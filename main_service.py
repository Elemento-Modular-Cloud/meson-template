import io
import traceback
import logging
import uuid
import os

from __init__ import __version__
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from commons.utils import (
    dynamic_global_import_fun,
    try_dynamic_import_fun
)
from errors.client_errors import (
    ElementoBadRequest,
    ElementoNotFound,
    BadRequestFieldError
)
from errors.server_errors import (
    ElementoCreationFailed,
    ElementoInternalServerError,
    ElementoServiceUnavailable,
)
from commons.elemento_iam import ElementoIdentityAccessManagement
from elemento_billing_manager.billing_manager import billing_manager, BillingStatus
from dotenv import load_dotenv
from typing import Any
from elogger.logger_manager_fastapi import setup_logging
from asgi_correlation_id import CorrelationIdMiddleware

load_dotenv()

root_path = ["platforms", "software"]
prefix = "service"
methods = [
    "get_service",
    "get_all_services",
    "setup_config",
    "create",
    "delete",
]
try:
    services = {}
    for path in root_path:
        try:
            service = dynamic_global_import_fun(
                folder_path=path, prefix=prefix, methods=methods
            )
            services.update(service)
        except Exception as error:
            logging.error(f"Error importing services from {path}: {error.__str__()}")
        
        if len(services.keys()) == 0:
            raise Exception("No services found in the specified paths.")
except Exception as error:
    logging.error(error.__str__())
    exit(1)

app = FastAPI(docs_url=None)
elemento_iam = ElementoIdentityAccessManagement()
setup_logging()

app.add_middleware(
    CorrelationIdMiddleware,
    header_name="X-Request-ID",
    update_request_header=True,
)


class HealthCheckFilter(logging.Filter):
    """Filter to skip logging for health check and root endpoints"""

    def filter(self, record):
        msg = record.getMessage()
        # Skip root endpoint (GET /) and health endpoint
        return not any(path in msg for path in ["GET /api/v1.0/health", "GET / HTTP/1.1"])


uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(HealthCheckFilter())

def get_service_or_import(service_name):
    if service_name in services and services[service_name] is not None:
        return services[service_name]

    try:
        services[service_name] = try_dynamic_import_fun(
            folder_path=root_path,
            prefix=prefix,
            service_name=service_name,
            methods=methods,
        )
        return services[service_name]
    except Exception as e:
        raise e


@app.get("/")
async def health():
    PlainTextResponse(
        status_code=200,
        content=f"Hello, world! This is an Elemento Services Meson for provider {os.getenv('PROVIDER')}.",
    )


@app.get("/api/v1.0/health")
def health():
    # TODO: perform a GET request and check the response to ensure the provider is healthy
    return JSONResponse(
        status_code=200,
        content={"status": "UP", "version": __version__,  "provider_status": "TODO"},
    )


@app.get("/api/v1.0/{service}/running")
@elemento_iam.validate_request
async def route_list_service(request: Request, service: str, token: Any = None):
    try:

        client_uuid = getattr(token, "client_uuid", None) or request.headers.get("client_uuid")
        
        client_uuid = str(uuid.UUID(client_uuid))

        try:
            current_service = get_service_or_import(service)
        except Exception:
            return ElementoServiceUnavailable(
                origin="MESON",
                error="Service unavailable",
                trace=traceback.format_exc(),
                meson_source="route_list_service()",
                service_failed=[service],
            )

        response, status_code = current_service["get_all_services"](client_uuid)

        if status_code == 200:
            return JSONResponse(status_code=200, content=response)
        else:
            return ElementoInternalServerError(
                origin="PROVIDER",
                error=f"Internal Server Error: {response}",
                trace=traceback.format_exc(),
                meson_source="route_list_service()",
            )

    except Exception as error:
        logging.error(str(error))
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="route_list_service()",
        )


@app.get("/api/v1.0/{service}/running/{service_uuid}")
@elemento_iam.validate_request
async def route_get_service_by_id(request: Request, service: str, service_uuid: str, token: Any = None):
    try:
        client_uuid = getattr(token, "client_uuid", None) or request.headers.get("client_uuid")
        client_uuid = str(uuid.UUID(client_uuid))
        try:
            current_service = get_service_or_import(service)
        except Exception:
            return ElementoServiceUnavailable(
                origin="MESON",
                error="Service unavailable",
                trace=traceback.format_exc(),
                meson_source="route_get_service_by_id()",
                service_failed=[service],
            )

        try:
            response, status_code = current_service["get_service"](service_uuid, client_uuid)
        except Exception as e:
            return JSONResponse(content="Not found", status_code=404)

        if status_code == 200 or status_code == 206:
            return JSONResponse(content=response, status_code=status_code)
        else:
            return ElementoInternalServerError(
                origin="PROVIDER",
                error=f"Internal Server Error: {response}",
                trace="",
                meson_source="get_service()",
            )

    except Exception as error:
        logging.error(f"route_get_service_by_id - {str(error)}")
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="route_get_service_by_id()",
            headers={"error": str(error)},
        )


@app.post("/api/v1.0/{service}/create")
@elemento_iam.validate_request
async def route_create_service(request: Request, service: str, background_tasks: BackgroundTasks, token: Any = None):
    billing_uuid = str(uuid.uuid4())
    client_uuid = None

    try:
        service_to_create = await request.json()
        region = service_to_create.get("region")
        client_uuid = getattr(token, "client_uuid", None) or request.headers.get("client_uuid") or service_to_create.get("client_uuid")
        client_uuid = str(uuid.UUID(client_uuid))
        interval = service_to_create.get("billing_frequency")

        if client_uuid is None:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="client_uuid",
                        where="HEADER",
                        error="MISSING",
                        type="str",
                        expected_value="",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="route_create_service()",
            )

        if interval is None:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="interval",
                        where="BODY",
                        error="MISSING",
                        type="str",
                        expected_value="",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="route_create_service()",
            )
        
        try:
            current_service = get_service_or_import(service)
        except Exception:
            return ElementoServiceUnavailable(
                origin="MESON",
                error="Service unavailable",
                trace=traceback.format_exc(),
                meson_source="route_create_service()",
                service_failed=[service],
            )
        
        try:
            cancreate_res, status_code = current_service["cancreate"](service_to_create)
            service_to_create = cancreate_res.get("payload", service_to_create)
        except Exception as e:
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during {service} creation trigger: {str(e)}",
                trace=traceback.format_exc(),
                meson_source="route_create_service()",
            )
        
        try:
            service_config = current_service["setup_config"](service_to_create, client_uuid)
        except Exception as e:
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during {service} setup config: {str(e)}",
                trace=traceback.format_exc(),
                meson_source="route_create_service()",
            )

        # --------- DEV BILLING BYPASS ---------
        # service_created, status_code = current_service["create"](service_to_create, client_uuid, billing_uuid)
        # return JSONResponse(
        #     status_code=status_code,
        #     content=service_created,
        # )
        # -----------------------------------

        # Essential to understand if billing must start or not
        billing_uuid = service_to_create.pop("billing_uuid", None)
        parent_billing_uuid = service_to_create.pop("parent_billing_uuid", None)
        # -- CREATE BILLING ENTRY --
        if not billing_uuid:
            service_to_create["client_uuid"] = client_uuid
            try:
                if parent_billing_uuid:
                    billing_uuid = billing_manager.start_sub(
                        client_uuid=client_uuid,
                        parent_billing_uuid=parent_billing_uuid,
                        payload=service_to_create,
                        service_type="service",
                        service_sub_type=service,
                        region=region,
                        provider=os.getenv("PROVIDER"),
                    )
                else:
                    payment_link, billing_uuid = billing_manager.start(
                        payload=service_to_create,
                        service_type="service",
                        service_sub_type=service,
                        client_uuid=client_uuid,
                        org=token.elemento_org or None,
                        interval=interval,
                        provider=os.getenv("PROVIDER"),
                        region=region,
                    )
                return JSONResponse(content={"payment_url": payment_link, "billing_uuid": str(billing_uuid)}, status_code=202)
            except Exception as e:
                logging.error(f"Error: {str(e)}")
                return JSONResponse(status_code=500, content={"error": "billing_failed", "details": str(e)})
        if token.elemento_role.lower() == 'portal':
            client_uuid = service_to_create.pop("client_uuid", None)
            client_uuid = str(uuid.UUID(client_uuid))
            billing_manager.update_status(billing_uuid, BillingStatus.PROVISIONING)
            try:
                service_config = current_service["setup_config"](service_to_create, client_uuid)
                service_created, status_code = current_service["create"](service_config, client_uuid, billing_uuid)

                if status_code == 202:
                    background_tasks.add_task(
                        current_service["complete_setup"], client_uuid, billing_uuid, service_to_create.get("name")
                    )
                    billing_manager.update_status(billing_uuid, BillingStatus.RUNNING)
                    return JSONResponse(
                        status_code=202,
                        content=service_created,
                    )
                if status_code == 200:
                    billing_manager.update_status(billing_uuid, BillingStatus.RUNNING)
                    return JSONResponse(
                        status_code=200,
                        content=service_created,
                    )
                else:
                    logging.error(f"Error during service creation: {traceback.format_exc()}")
                    billing_manager.update_status(billing_uuid, BillingStatus.ERROR)
                    return ElementoInternalServerError(
                        origin="PROVIDER",
                        error=f"Immediate provider error: {service_created}",
                        trace=traceback.format_exc(),
                        meson_source="route_create_service()",
                    )

            except Exception:
                logging.error(f"Error during service creation trigger: {traceback.format_exc()}")
                billing_manager.update_status(billing_uuid, BillingStatus.ERROR)
                return ElementoCreationFailed(
                    origin="MESON",
                    error=f"Error during {service} creation trigger",
                    trace=traceback.format_exc(),
                    stopped_successfully=True,
                    billing_suspended=True,
                    meson_source="route_create_service()",
                )

        else:
            logging.error("Not Authorized")
            return ElementoCreationFailed(
                origin="MESON",
                error="Not authorized",
                trace=traceback.format_exc(),
                meson_source="route_create_service()",
            )

    except Exception as error:
        logging.error(str(error))
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="route_create_service()",
        )


@app.delete("/api/v1.0/{service}/delete")
@elemento_iam.validate_request
async def route_delete_service(request: Request, service: str, background_tasks: BackgroundTasks, token: Any = None):
    try:
        service_to_delete = await request.json()
        client_uuid = getattr(token, "client_uuid", None) or request.headers.get("client_uuid") or service_to_delete.get("client_uuid")
        client_uuid = str(uuid.UUID(client_uuid))
        target_uuid = service_to_delete.get("service_uuid", "")
        billing_uuid = None

        try:
            current_service = get_service_or_import(service)
        except Exception:
            return ElementoServiceUnavailable(
                origin="MESON",
                error="Service unavailable",
                trace=traceback.format_exc(),
                meson_source="route_delete_service()",
                service_failed=[service],
            )

        # --------- DEV BILLING BYPASS ---------
        # response, status_code = current_service["delete"](target_uuid, client_uuid)
        # return JSONResponse(
        #     status_code=status_code,
        #     content=response,
        # )
        # -----------------------------------

        role = token.elemento_role.lower()

        if role == 'portal':
            client_uuid = service_to_delete.get("client_uuid")
            client_uuid = str(uuid.UUID(client_uuid))
            try:
                response, status_code = current_service["get_service"](target_uuid, client_uuid)
                if status_code != 200:
                    raise Exception("Not found")
            except Exception:
                return ElementoNotFound(
                    origin="MESON",
                    error=f"Service with UID {target_uuid} not found",
                    trace=traceback.format_exc(),
                    meson_source="route_get_service_by_id()",
                )
            
            billing_uuid = response.get("billing_uuid")
            
            try:
                response, status_code = current_service["delete"](target_uuid, client_uuid)
                if status_code == 200:
                    billing_manager.update_status(billing_uuid, BillingStatus.DELETED)
                    background_tasks.add_task(current_service["perform_full_delete"], client_uuid, target_uuid)
                    return JSONResponse(
                        status_code=200,
                        content=f"{service} with id {target_uuid} deletion started",
                    )
                else:
                    logging.error(f"Error during service deletion: {traceback.format_exc()}")
                    billing_manager.update_status(billing_uuid, BillingStatus.ERROR)
                    return ElementoInternalServerError(
                        origin="PROVIDER",
                        error=f"Internal Server Error: {response}",
                        trace=traceback.format_exc(),
                        meson_source="route_delete_service()",
                    )
            except Exception:
                logging.error(f"Error during service deletion trigger: {traceback.format_exc()}")
                billing_manager.update_status(billing_uuid, BillingStatus.ERROR)
                return ElementoInternalServerError(
                    origin="MESON",
                    error=f"Error during {service} delete trigger",
                    trace=traceback.format_exc(),
                    meson_source="route_delete_service()",
                )

        else:
            try:
                response, status_code = current_service["get_service"](target_uuid, client_uuid)
                if status_code != 200:
                    raise Exception("Not found")
            except Exception:
                logging.error(f"Service with UID {target_uuid} not found: {traceback.format_exc()}")
                return ElementoNotFound(
                    origin="MESON",
                    error=f"Service with UID {target_uuid} not found",
                    trace=traceback.format_exc(),
                    meson_source="route_get_service_by_id()",
                )
            
            billing_uuid = response.get("billing_uuid")
            service_to_delete['client_uuid'] = client_uuid
            res = billing_manager.update_status(
                billing_uuid, BillingStatus.TO_DELETE, service_type="service", service_sub_type=service, payload=service_to_delete
            )

            if res is not None:
                return JSONResponse(status_code=202, content={"status": "to_delete", "billing_uuid": billing_uuid})
            else:
                logging.error(f"Failed to mark resource as to_delete on billing side: {traceback.format_exc()}")
                billing_manager.update_status(billing_uuid, BillingStatus.ERROR)
                return ElementoInternalServerError(
                    origin="MESON",
                    error="Failed to mark resource as to_delete on billing side",
                    trace=traceback.format_exc(),
                    meson_source="route_delete_service()",
                )

    except Exception as error:
        logging.error(str(error))
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="route_delete_service()",
        )


@app.get("/api/v1.0/{service}/credentials/{service_uuid}")
@elemento_iam.validate_request
async def route_get_credentials(request: Request, service: str, service_uuid: str, token: Any = None):
    try:
        client_uuid = getattr(token, "client_uuid", None) or request.headers.get("client_uuid")
        client_uuid = str(uuid.UUID(client_uuid))

        try:
            current_service = get_service_or_import(service)
        except Exception:
            return ElementoServiceUnavailable(
                origin="MESON",
                error="Service unavailable",
                trace=traceback.format_exc(),
                meson_source="route_get_credentials()",
                service_failed=[service],
            )
            
        try:
            _, status_code = current_service["get_service"](service_uuid, client_uuid)
            if status_code != 200:
                raise Exception("Not found")
        except Exception:
            return ElementoNotFound(
                origin="MESON",
                error=f"Service with UID {service_uuid} not found",
                trace=traceback.format_exc(),
                meson_source="route_get_service_by_id()",
            )

        try:
            creds_response, status_code = current_service["get_credentials"](client_uuid, service_uuid)
        except Exception:
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during key rotation for {service_uuid}",
                trace=traceback.format_exc(),
                meson_source="route_get_credentials()",
            )

        if status_code in [200, 201]:
            file_stream = io.StringIO(creds_response)

            return StreamingResponse(
                iter([file_stream.getvalue()]),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=credentials_{service_uuid}.txt"},
            )
        elif status_code == 400:
            return ElementoBadRequest(
                origin="PROVIDER",
                error=creds_response.get("error", f"{service} in creation: {service_uuid}"),
                field_errors=[],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="route_get_credentials()",
            )
        elif status_code in [403, 404]:
            return ElementoNotFound(
                origin="PROVIDER",
                error=f"{service} not found: {service_uuid}",
                trace=traceback.format_exc(),
                meson_source="route_get_credentials()",
            )

        else:
            return ElementoInternalServerError(
                origin="PROVIDER",
                error=f"Internal Server Error: {creds_response}",
                trace="",
                meson_source="route_get_credentials()",
            )

    except Exception as error:
        logging.error(f"route_get_credentials - {str(error)}")
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="route_get_credentials()",
            headers={"error": str(error)},
        )


@app.post("/api/v1.0/{service}/cancreate")
@elemento_iam.validate_request
async def route_cancreate(request: Request, service: str, token: Any = None):
    try:
        payload = await request.json()
        client_uuid = getattr(token, "client_uuid", None) or request.headers.get("client_uuid")
        client_uuid = str(uuid.UUID(client_uuid))
        region = payload.get("region")

        logging.debug(f"Received cancreate request with payload: {payload}")

        try:
            current_service = services.get(service)
            if not current_service:
                raise ValueError(f"Service {service} not found")
        except Exception:
            logging.debug(f"Service {service} not found")
            return ElementoServiceUnavailable(
                origin="MESON",
                error="Service unavailable",
                trace=traceback.format_exc(),
                meson_source="get_service_or_import()",
                service_failed=[service],
            )
        
        try:
            service_config = current_service["setup_config"](payload, client_uuid)
        except Exception as e:
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during {service} setup config: {str(e)}",
                trace=traceback.format_exc(),
                meson_source="route_cancreate()",
            )

        try:
            cancreate_res, status_code = current_service["cancreate"](service_config)
        except Exception as e:
            logging.debug(f"Error during getting create options for {service}: {str(e)}")
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during getting create options for {service}: {str(e)}",
                trace=traceback.format_exc(),
                meson_source="route_cancreate()",
            )

        price_value = None
        if status_code == 200:
            try:
                price_info = billing_manager.get_price(
                    payload=cancreate_res.get("payload"),
                    service_type="service",
                    service_sub_type=service,
                    client_uuid=client_uuid,
                    org=token.elemento_org or None,
                    provider=os.getenv("PROVIDER", "upcloud"),
                    region=region,
                    interval=payload.get("billing_frequency"),
                )

                if isinstance(price_info, dict):
                    logging.debug(f"Received price info: {price_info}")
                    price_value = price_info.get("total_net")

            except Exception as e:
                price_value = None
                cancreate_res['cancreate'] = False
                logging.error(f"Error fetching price info: {str(e)}")

            return {
                "cancreate": cancreate_res.get("cancreate"),
                "billing": [{"price_net": price_value, "period": payload.get("billing_frequency")}],
                "provider": os.getenv("PROVIDER", "upcloud"),
            }

        elif status_code == 400:
            logging.debug(f"Can create {service} - bad request: {cancreate_res.get('reasons')}")
            return {
                "cancreate": cancreate_res.get("cancreate"),
                "billing": [],
                "provider": os.getenv("PROVIDER", "upcloud"),
                "reasons": cancreate_res.get("reasons", {"general": "Unknown reason"}),
            }

        else:
            return ElementoBadRequest(
                origin="PROVIDER",
                error=cancreate_res.get("error", f"Bad request for {service}"),
                field_errors=[],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="route_cancreate()",
            )

    except Exception as error:
        logging.error(f"route_cancreate generic error - {str(error)}")
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="route_cancreate()",
            headers={"error": str(error)},
        )
