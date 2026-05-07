import io
import json
import traceback
import logging
import uuid
import os

from __init__ import __version__
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from commons.utils import (
    get_from_dict,
    dynamic_global_import_fun,
    try_dynamic_import_fun
)
from errors.client_errors import (
    ElementoBadRequest,
    ElementoNotFound,
    BadRequestFieldError, ElementoTooEarly
)
from errors.server_errors import (
    ElementoCreationFailed,
    ElementoInternalServerError,
    ElementoServiceUnavailable,
)
from commons.elemento_iam import ElementoIdentityAccessManagement
from elemento_billing_manager.billing_manager import billing_manager
from dotenv import load_dotenv
from typing import Any

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

class HealthCheckFilter(logging.Filter):
    """Filter to skip logging for health check and root endpoints"""

    def filter(self, record):
        msg = record.getMessage()
        # Skip root endpoint (GET /) and health endpoint
        return not any(path in msg for path in ["GET /api/v1.0/health", "GET / HTTP/1.1"])


uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(HealthCheckFilter())


# This is an example implementation for the routing of services supported on this specific provider.

@app.get("/")
async def health():
    PlainTextResponse(
        status_code=200,
        content=f"Hello, world! This is an Elemento Services Meson for provider {os.getenv('PROVIDER')}.",
    )


@app.get("/api/v1.0/health")
def health():
    return JSONResponse(
        status_code=200,
        content={"status": "UP", "version": __version__},
    )


@app.get("/api/v1.0/{service}/running")
@elemento_iam.validate_request
async def service_description(request: Request, service: str):
    try:
        client_uuid = request.headers.get("client_uuid")

        try:
            service_country = (
                request.headers["service_country"]
                if "service_country" in request.headers.keys()
                else os.getenv("PROVIDER_REGION")
            )
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request in 1 field",
                field_errors=[
                    BadRequestFieldError(
                        field="service_country",
                        where="HEADER",
                        error="MISSING",
                        type="str",
                        expected_value="",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="service_description()",
            )

        if services.get(service) is not None:
            response, status_code = services[service]["get_all_services"](
                client_uuid, service_country
            )
        else:
            try:
                services[service] = try_dynamic_import_fun(
                    folder_path=root_path,
                    prefix=prefix,
                    service_name=service,
                    methods=methods,
                )
                response, status_code = services[service]["get_all_services"](
                    client_uuid, service_country
                )
            except Exception as error:
                return ElementoServiceUnavailable(
                    origin="MESON",
                    error="Service unavailable",
                    trace=traceback.format_exc(),
                    meson_source="service_description()",
                    service_failed=[service],
                )

        if status_code==200:
            return JSONResponse(status_code=200, content=response)
        else:
            return ElementoInternalServerError(
                origin="PROVIDER",
                error = f"Internal Server Error: {response}",
                trace=traceback.format_exc(),
                meson_source="service_description()",
            )

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="service_description()",
        )
    

@app.get("/api/v1.0/{service}/running/{service_uid}")
@elemento_iam.validate_request
async def service_description_by_id(request: Request, service: str, service_uid: str):
    try:
        client_uuid = request.headers.get("client_uuid")
    
        try:
            service_country = (
                request.headers["service_country"]
                if "service_country" in request.headers.keys()
                else os.getenv("PROVIDER_REGION")
            )
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request in 1 field",
                field_errors=[
                    BadRequestFieldError(
                        field="service_country",
                        where="HEADER",
                        error="MISSING",
                        type="str",
                        expected_value="",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="service_description()",
            )
        
        try:
            if services.get(service) is not None:
                response, status_code = services[service]["get_service"](
                    service_uid, client_uuid, service_country
                )
            else:
                try:
                    services[service] = try_dynamic_import_fun(
                        folder_path=root_path,
                        prefix=prefix,
                        service_name=service,
                        methods=methods,
                    )
                    response, status_code = services[service]["get_service"](
                        service_uid, client_uuid, service_country
                    )
                except Exception as error:
                    return ElementoServiceUnavailable(
                        origin="MESON",
                        error="Service unavailable",
                        trace=traceback.format_exc(),
                        meson_source="service_description()",
                        service_failed=[service],
                    )
        except Exception as error:
            return ElementoNotFound(
                origin='MESON',
                error=f'Service with UID {service_uid} not found',
                trace=traceback.format_exc(),
                meson_source='get_service()'
            )

        if status_code==200 or status_code==206:
            return JSONResponse(content=response, status_code=status_code)
        else:
            return ElementoInternalServerError(
                origin="PROVIDER",
                error = f"Internal Server Error: {response}",
                trace="",
                meson_source="get_service()",
            )

    except Exception as error:
        logging.error("server_description_by_id -", error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="servers_description_by_id()",
            headers={"error": error.__str__()},
        )


@app.post("/api/v1.0/{service}/create")
@elemento_iam.validate_request
async def create_service(request: Request, service: str):
    billing_uuid = None
    client_uuid = None
    try:
        service_to_create = await request.json()
        service_country = (
            request.headers["service_country"]
            if "service_country" in request.headers.keys()
            else os.getenv("PROVIDER_REGION")
        )
        async_flag = "false"
        if request.headers.get("Async") is not None:
            async_flag = request.headers.get("Async")
        req_data = (
            get_from_dict(service_to_create, "req")
            if type(service_to_create) == dict
            else json.loads(get_from_dict(service_to_create, "req"))
        )
        client_uuid = get_from_dict(service_to_create, "client_uuid")

        ##* Verify presence of service
        if services.get(service) is None:
            try:
                services[service] = try_dynamic_import_fun(
                    folder_path=root_path,
                    prefix=prefix,
                    service_name=service,
                    methods=methods,
                )
            except Exception as error:
                return ElementoServiceUnavailable(
                    origin="MESON",
                    error="Service unavailable",
                    trace=traceback.format_exc(),
                    meson_source="create_service()",
                    service_failed=[service],
                )

        ##* SETUP CONFIG
        try:
            service_config = services[service]["setup_config"](
                req_data, client_uuid, service_country
            )
        except Exception as error:
            return ElementoInternalServerError(
                origin="MESON",
                error="Internal Server Error",
                trace=traceback.format_exc(),
                meson_source="create_service()",
            )

        ##* SERVICE CREATION
        try:
            # -- START BILLING --
            # Pick or add a service model from elemento_billing_manager directory
            # specs = YourServiceModel(
            #     provider=os.getenv("PROVIDER", "wasabi"),
            #     region=service_to_create.get("region", os.getenv("WASABI_DEFAULT_REGION", "eu-central-1")),
            #     versioning_enabled=False,
            #     max_quota_gb=400,
            # )
            specs = None
            billing_uuid = billing_manager.start(client_uuid, specs, "storage", "objectstorage", None) #TODO: capire come passare i parametri corretti
            # -------------------

            service_created, status_code = services[service]["create"](
                service_config, client_uuid, billing_uuid
            )
        except Exception as error:
            # -- STOP BILLING --
            billing_manager.stop(billing_uuid, client_uuid)
            # ------------------
            logging.error(f"Error during {service} creation: {error.__str__()}")
            return ElementoCreationFailed(
                origin="MESON",
                error=f"Error during {service} creation",
                trace=traceback.format_exc(),
                stopped_successfully=True,
                billing_suspended=True,
                meson_source="create_service()",
            )

        if status_code==200:
            return JSONResponse(status_code=status_code, content=service_created.to_json())
        else:
            # -- STOP BILLING --
            billing_manager.stop(billing_uuid, client_uuid)
            # ------------------
            logging.error("Service creation failed: %s", service_created)
            return ElementoInternalServerError(
                origin="PROVIDER",
                error = f"Internal Server Error: {service_created}",
                trace=traceback.format_exc(),
                meson_source="create_service()",
            )

    except Exception as error:
        # -- STOP BILLING --
        billing_manager.stop(billing_uuid, client_uuid)
        # ------------------    
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="create_service()",
        )


@app.delete("/api/v1.0/{service}/delete")
@elemento_iam.validate_request
async def delete_service(request: Request, service: str):
    billing_uuid = None
    try:
        service_to_delete = await request.json()
        service_country = (
            request.headers["service_country"]
            if "service_country" in request.headers.keys()
            else os.getenv("PROVIDER_REGION")
        )
        client_uuid = get_from_dict(service_to_delete, "client_uuid")
        service_uid = get_from_dict(service_to_delete, "id")

        ##* Verify presence of service
        if services.get(service) is None:
            try:
                services[service] = try_dynamic_import_fun(
                    folder_path=root_path,
                    prefix=prefix,
                    service_name=service,
                    methods=methods,
                )
            except Exception as error:
                return ElementoServiceUnavailable(
                    origin="MESON",
                    error="Service unavailable",
                    trace=traceback.format_exc(),
                    meson_source="delete_service()",
                    service_failed=[service],
                )

        if service_uid is None:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="id",
                        where="BODY",
                        error="MISSING",
                        type="str",
                        expected_value="",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="delete_service()",
            )

        ##* DELETE
        try:
            billing_uuid, status_code = (
                services[service]["get_service"](
                    service_uid, client_uuid, service_country, True
                )
                if service_to_delete.get("metadata") is None
                else services[service]["get_service"](
                    service_to_delete.get("metadata"),
                    service_uid,
                    client_uuid,
                    service_country,
                )
            )
            if status_code != 200:
                raise Exception(f"Service delete failed: {billing_uuid}, status_code: {status_code}")
        except Exception as error:
            return ElementoNotFound(
                origin='MESON',
                error=f'Service with UID {service_uid} not found',
                trace=traceback.format_exc(),
                meson_source='get_service()'
            )

        try:
            response, status_code = services[service]["delete"](
                service_uid, client_uuid, service_country
            )
            if status_code == 200:
                # -- STOP BILLING --
                billing_manager.stop(billing_uuid, client_uuid)
                # ------------------
                return JSONResponse(
                    status_code=200,
                    content=f"{service} with id {service_to_delete.get("service_uuid")} deleted successfully",
                )
            else:
                return ElementoInternalServerError(
                    origin="PROVIDER",
                    error=f"Internal Server Error: {response}",
                    trace=traceback.format_exc(),
                    meson_source="delete_service()",
                )
        except Exception as error:
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during {service} delete",
                trace=traceback.format_exc(),
                meson_source="delete_service()",
            )

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="delete_service()",
        )


@app.get("/api/v1.0/{service}/credentials/{service_uuid}")
@elemento_iam.validate_request
async def get_credentials_route(request: Request, service: str, service_uuid: str, token: Any = None):
    try:
        client_uuid = getattr(token, "client_uuid", None) or request.headers.get("client_uuid")
        client_uuid = str(uuid.UUID(client_uuid))

        ##* Verify presence of service
        if services.get(service) is None:
            try:
                services[service] = try_dynamic_import_fun(
                    folder_path=root_path,
                    prefix=prefix,
                    service_name=service,
                    methods=methods,
                )
            except Exception as error:
                return ElementoServiceUnavailable(
                    origin="MESON",
                    error="Service unavailable",
                    trace=traceback.format_exc(),
                    meson_source="delete_service()",
                    service_failed=[service],
                )
        
        if service_uuid is None:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="id",
                        where="BODY",
                        error="MISSING",
                        type="str",
                        expected_value="",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="delete_service()",
            )
            
        try:
            creds_response, status_code = services[service]["get_credentials"](client_uuid, service_uuid)
        except Exception:
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during key rotation for {service_uuid}",
                trace=traceback.format_exc(),
                meson_source="get_credentials()",
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
                meson_source="get_credentials()",
            )
        elif status_code in [403, 404]:
            return ElementoNotFound(
                origin="PROVIDER",
                error=f"{service} not found: {service_uuid}",
                trace=traceback.format_exc(),
                meson_source="get_credentials()",
            )

        else:
            return ElementoInternalServerError(
                origin="PROVIDER",
                error=f"Internal Server Error: {creds_response}",
                trace="",
                meson_source="get_credentials()",
            )

    except Exception as error:
        logging.error(f"get_credentials_route - {str(error)}")
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="get_credentials_route()",
            headers={"error": str(error)},
        )


@app.post("/api/v1.0/{service}/cancreate")
@elemento_iam.validate_request
async def cancreate(request: Request, service: str, token: Any = None):
    try:
        payload = await request.json()
        client_uuid = getattr(token, "client_uuid", None) or request.headers.get("client_uuid")
        client_uuid = str(uuid.UUID(client_uuid))
        region = payload.get("region")

        try:
            current_service = services.get(service)
            if not current_service:
                raise ValueError(f"Service {service} not found")
        except Exception:
            return ElementoServiceUnavailable(
                origin="MESON",
                error="Service unavailable",
                trace=traceback.format_exc(),
                meson_source="get_service_or_import()",
                service_failed=[service],
            )

        try:
            cancreate_res, status_code = current_service["cancreate"](payload)
        except Exception as e:
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during getting create options for {service}: {str(e)}",
                trace=traceback.format_exc(),
                meson_source="cancreate()",
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
            logging.error(f"Error in cancreate {cancreate_res.get('error')} for service {service}")
            return {
                "cancreate": cancreate_res.get("cancreate"),
                "billing": [],
                "provider": os.getenv("PROVIDER", "upcloud"),
            }

        else:
            return ElementoBadRequest(
                origin="PROVIDER",
                error=cancreate_res.get("error", f"Bad request for {service}"),
                field_errors=[],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="cancreate()",
            )

    except Exception as error:
        logging.error(f"cancreate generic error - {str(error)}")
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="cancreate()",
            headers={"error": str(error)},
        )
