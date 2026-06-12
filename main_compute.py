import io
import json
import logging
import os
import re
import traceback
import uuid
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from starlette.responses import StreamingResponse

from __init__ import __version__
from commons.elemento_iam import ElementoIdentityAccessManagement
from commons.utils import get_from_dict
from elemento_billing_manager.billing_manager import BillingStatus, billing_manager
from elemento_marketplace.cloudinit_manager import cloudinit_manager
from errors.client_errors import (
    BadRequestFieldError,
    ElementoBadRequest,
    ElementoNotFound,
    ElementoTooEarly,
)
from errors.server_errors import ElementoInternalServerError
from infrastructure.compute.compute_manager import (
    create_compute,
    get_compute_metrics,
    get_compute_by_uuid,
    is_compute_config_available,
    list_compute,
    delete_compute,
    restart_compute,
    start_compute,
    stop_compute,
)
from models.ComputeModel import VmModel
from elogger.logger_manager_fastapi import setup_logging
from asgi_correlation_id import CorrelationIdMiddleware

load_dotenv()

elemento_iam = ElementoIdentityAccessManagement()
app = FastAPI(docs_url=None)
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


@app.get("/")
def health():
    return PlainTextResponse(
        status_code=200,
        content=f"Hello, world! This is an Elemento Compute Meson for provider {os.getenv('PROVIDER')}",
    )


@app.get("/api/v1.0/health")
def health_check():
    # TODO: perform a GET request and check the response to ensure the provider is healthy
    return JSONResponse(
        status_code=200,
        content={"status": "UP", "version": __version__, "provider_status": "TODO"},
    )


@app.get("/api/v1.0/running")
@elemento_iam.validate_request
async def route_list_compute(request: Request, token: Any = None):
    try:
        client_uuid = str(uuid.UUID(str(getattr(token, "client_uuid"))))
        list_vms = list_compute(client_uuid)
        return JSONResponse(status_code=200, content={"vms": list_vms})
    
    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="route_list_compute()",
        )


@app.get("/api/v1.0/running/{vm_uuid}")
@elemento_iam.validate_request
async def route_get_compute_by_uuid(request: Request, vm_uuid: str, token: Any = None):
    try:
        client_uuid = str(uuid.UUID(str(getattr(token, "client_uuid"))))
        server_info = get_compute_by_uuid(client_uuid, vm_uuid)
        return JSONResponse(status_code=200, content=server_info)

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            meson_source="route_get_compute_by_uuid()",
            trace=traceback.format_exc(),
        )


@app.post("/api/v1.0/register")
@elemento_iam.validate_request
async def route_create_compute(request: Request, token: Any = None):
    billing_uuid = None
    try:
        try:
            auth_header = request.headers.get("Authorization")
            org = token.elemento_org
            servers_to_create = await request.json()
            role = token.elemento_role.lower()
            client_uuid = str(uuid.UUID(str(getattr(token, "client_uuid"))))
            billing_uuid = servers_to_create.pop("billing_uuid", None)
            parent_billing_uuid = servers_to_create.pop("parent_billing_uuid", None)

        except Exception as e:
            logging.error("Missing field: %s", e)
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Internal Server Error - {e.__str__()}",
                trace=traceback.format_exc(),
                meson_source="route_create_compute()",
            )
            
        try:
            vm = VmModel.from_json(servers_to_create, client_uuid)
        except Exception as ex:
            logging.error(ex.__str__())
            return ElementoBadRequest(
                origin="MESON",
                error=f"Bad Request - {ex}",
                field_errors=[],
                docs_url="",
                trace=f"{traceback.format_exc()}",
                meson_source="route_create_compute()",
            )

        try:
            ComputeModel.from_json_canallocate(servers_to_create)
            config_json = servers_to_create["req"] if "req" in servers_to_create else servers_to_create
            if "volumes" in servers_to_create and isinstance(servers_to_create["volumes"], list):
                for volume in servers_to_create["volumes"]:
                    if isinstance(volume, dict):
                        volume["type"] = "vm:hyperdisk-balanced"
            
            plan_name, zone_name = is_compute_config_available(config_json, servers_to_create.get("region"))
            if plan_name is None:
                logging.debug(f"Configuration not available - vm_size_name: {plan_name}")
                return ElementoBadRequest(
                    origin="MESON",
                    error="Requested configuration is not available",
                    field_errors=[],
                    docs_url="",
                    trace=f"{traceback.format_exc()}",
                    meson_source="route_create_compute()",
                )
            else:
                servers_to_create['flavour'] = plan_name
        except Exception as ex:
            logging.error(ex.__str__())
            return ElementoBadRequest(
                origin="MESON",
                error=f"Bad Request - {ex}",
                field_errors=[],
                docs_url="",
                trace=f"{traceback.format_exc()}",
                meson_source="route_create_compute()",
            )

        billing_zone = zone_name if zone_name else servers_to_create.get("region")
        
        if not billing_uuid:
            servers_to_create['client_uuid'] = client_uuid
            try:
                if parent_billing_uuid:
                    billing_uuid = billing_manager.start_sub(
                        client_uuid=client_uuid,
                        parent_billing_uuid=parent_billing_uuid,
                        payload=servers_to_create,
                        org=org,
                        service_type="matcher",
                        service_sub_type="vm",
                        region=billing_zone,
                        provider=os.getenv("PROVIDER"),
                    )
                else:
                    payment_link, billing_uuid = billing_manager.start(
                        payload=servers_to_create,
                        service_type="matcher",
                        service_sub_type="vm",
                        client_uuid=client_uuid,
                        org=org,
                        interval=servers_to_create.get("billing_frequency", "month"),
                        provider=os.getenv("PROVIDER"),
                        region=billing_zone,
                    )
                return JSONResponse(status_code=202, content={"payment_url": payment_link, "billing_uuid": str(billing_uuid)})

            except Exception as e:
                logging.error(f"Error: {str(e)}")
                return JSONResponse(status_code=500, content={"error": "billing_failed", "details": str(e)})

        if role == "portal":
            vm.billing_uuid = billing_uuid
            billing_manager.update_status(billing_uuid, BillingStatus.PROVISIONING)
            try:
                client_uuid = servers_to_create.get('client_uuid')
                create_compute(servers_to_create, client_uuid, billing_uuid, auth_header)
                billing_manager.update_status(billing_uuid, BillingStatus.RUNNING)
                return JSONResponse(content=vm.to_json_register(), status_code=200)

            except Exception as ex:
                # -- STOP BILLING --
                billing_manager.update_status(billing_uuid, BillingStatus.ERROR)
                # ------------------
                logging.error(ex.__str__())
                return ElementoInternalServerError(
                    origin="MESON",
                    error=f"Internal Server Error - {ex}",
                    trace=f"{traceback.format_exc()}",
                )
    except Exception as e:
        logging.error(f"Unexpected error occurred: {str(e)}")
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {e}",
            trace=f"{traceback.format_exc()}",
        )


@app.get("/api/v1.0/canallocate")
@elemento_iam.validate_request
async def route_canallocate(request: Request, token: Any = None):
    try:
        body = await request.json()

        if isinstance(body, str):
            body = json.loads(body)

        try:
            ComputeModel.from_json_canallocate(body)
        except Exception as ex:
            logging.debug(f"Error during config validation: {str(ex)}")
            return ElementoBadRequest(
                origin="MESON",
                error=f"Bad Request - Invalid format: {ex}",
                field_errors=[],
                docs_url="",
                trace=f"{traceback.format_exc()}",
                meson_source="route_canallocate()",
            )
        if "volumes" in body and isinstance(body["volumes"], list):
            for volume in body["volumes"]:
                if isinstance(volume, dict):
                    volume["type"] = "vm:hyperdisk-balanced"

        config_json = body["req"] if "req" in body else body
        logging.debug(f"Configurazione estratta: {config_json.get('misc', 'No Misc')}")

        cloudinit_data = body.get("cloudinit") if isinstance(body.get("cloudinit"), dict) else {}
        cloudinit_template = cloudinit_data.get("template") if cloudinit_data else None
        
        if cloudinit_template:
            if config_json.get("misc", {}).get("os_family", "").lower() == "windows":
                return {
                    "cancreate": False,
                    "billing": [],
                    "provider": os.getenv("PROVIDER", "provider"),
                }
                
            try:
                logging.debug(f"Attempting to load cloud-init template: {cloudinit_template}")
                cloudinit_script, metadata = cloudinit_manager.load_template_with_prerequisites(
                    template_name=cloudinit_template, variables=cloudinit_data.get("variables", {})
                )

                logging.debug(f"Cloud-init template {cloudinit_template} loaded and added to metadata.")

                prerequisites = {}
                if isinstance(metadata, dict):
                    prerequisites = metadata.get("prerequisites", {})
                    if not isinstance(prerequisites, dict):
                        prerequisites = {}

                if "storage" in prerequisites and isinstance(prerequisites.get("storage"), list):
                    for storage_req in prerequisites["storage"]:
                        if len(body.get("volumes", [])) == 0:
                            raise ValueError(
                                f"Cloud-init prerequisite not met: requires at least {storage_req.get('min_size_gb')} GB disk, but no volumes provided."
                            )
                        if (
                            body.get("volumes")
                            and len(body["volumes"]) > 0
                            and body["volumes"][0].get("size") < storage_req.get("min_size_gb", 0)
                        ):
                            raise ValueError(
                                f"Cloud-init prerequisite not met: requires at least {storage_req.get('min_size_gb')} GB disk."
                            )

                if "resources" in prerequisites and isinstance(prerequisites.get("resources"), dict):
                    resources_req = prerequisites["resources"]
                    
                    slots = config_json.get("cpu", {}).get("slots", 1)
                    capacity = config_json.get("mem", {}).get("capacity", 0)

                    if slots < resources_req.get("min_cpu", 0):
                        raise ValueError(f"Cloud-init prerequisite not met: requires at least {resources_req.get('min_cpu')} CPU slots.")
                    if capacity < resources_req.get("min_memory_gb", 0) * 1024:
                        raise ValueError(
                            f"Cloud-init prerequisite not met: requires at least {resources_req.get('min_memory_gb')} GB memory."
                        )

            except FileNotFoundError as e:
                logging.error(f"Cloud-init template not found: {e}")
                raise ValueError(f"Cloud-init template '{cloudinit_template}' not found. {str(e)}")

        plan_name, zone_name = is_compute_config_available(config_json, body.get("region"))

        if plan_name is None:
            logging.debug(f"Configuration not available - vm_size_name: {plan_name}")
            return {
                "cancreate": False,
                "billing": [],
                "provider": os.getenv("PROVIDER", "provider"),
            }

        password = body.get("authentication", {}).get("password") if isinstance(body.get("authentication"), dict) else None
        if password:
            errors = []

            if len(password) < 8:
                errors.append("at least 8 characters")
            if not re.search(r'\d', password):
                errors.append("at least one number")
            if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', password):
                errors.append("at least one symbol")

            if errors:
                return ElementoBadRequest(
                    origin="MESON",
                    error=f"Password must contain: {', '.join(errors)}",
                    field_errors=[
                        BadRequestFieldError(
                            field="password",
                            type="string",
                            expected_value="minimum 8 characters with numbers and symbols",
                            where="BODY",
                            error="INVALID_PASSWORD",
                        )
                    ],
                    docs_url="",
                    trace="",
                    meson_source="route_canallocate()",
                )

        body['flavour'] = plan_name
        billing_zone = zone_name if zone_name else body.get("region")

        try:
            price_info = billing_manager.get_price(
                payload=body,
                service_type="matcher",
                service_sub_type="vm",
                client_uuid=token.client_uuid,
                org=token.elemento_org or None,
                provider=os.getenv("PROVIDER", "provider"),
                region=billing_zone,
                interval=body.get("billing_frequency", "month"),
            )

            if isinstance(price_info, dict):
                price_value = price_info.get("total_net")
                logging.debug(f"Price info retrieved successfully: {price_info}")

        except Exception as e:
            price_value = None
            logging.error(f"Error fetching price info: {str(e)}")

        if price_value is None:
            logging.debug(f"Configuration not available - vm_size_name: {plan_name}")
            return {
                "cancreate": False,
                "billing": [],
                "provider": os.getenv("PROVIDER", "provider"),
            }

        logging.debug(f"Configuration can be allocated - vm_size_name: {plan_name}, price: {price_value}")
        return {
            "cancreate": True,
            "billing": [{"price_net": price_value, "period": body.get("billing_frequency", "month")}],
            "provider": os.getenv("PROVIDER", "provider"),
        }

    except Exception as error:
        logging.error(f"Error in canallocate: {str(error)}")
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error}",
            trace=traceback.format_exc(),
            meson_source="route_canallocate()",
        )      
        

@app.delete("/api/v1.0/unregister")
@elemento_iam.validate_request
async def route_delete_compute(request: Request, token: Any = None):
    try:
        to_destroy = await request.json()
        client_uuid = str(uuid.UUID(str(getattr(token, "client_uuid"))))
        vm_uuid = to_destroy.get("vm_uid") or to_destroy.get("vm_id")
        role = token.elemento_role.lower()
        auth_header = request.headers.get("Authorization")

        if not vm_uuid:
            return JSONResponse(content={"response": "Wrong json parsed: missing vm_uid"}, status_code=400)

        if role == "portal":
            target_client = to_destroy.get("client_uuid") or to_destroy.get("client_uid") or client_uuid
            billing_uuid = None
            try:
                billing_uuid = delete_compute(client_uuid=str(target_client), vm_uuid=vm_uuid, auth_token=auth_header)
                if billing_uuid:
                    billing_manager.update_status(billing_uuid, BillingStatus.DELETED)
                
                return JSONResponse(
                    content={
                        "unregistered": True,
                        "uniqueID": vm_uuid,
                    },
                    status_code=200,
                )
            except Exception as e:
                logging.error(str(e))
                if billing_uuid:
                    billing_manager.update_status(billing_uuid, BillingStatus.ERROR)
                return ElementoInternalServerError(
                    origin="MESON",
                    error=f"Delete failed: {e}",
                    trace=traceback.format_exc(),
                    meson_source="route_delete_compute()",
                )
        
        else:
            billing_uuid = None
            try:
                to_destroy['client_uuid'] = client_uuid
                billing_uuid = get_billing_uuid(vm_uuid)
                
                res = billing_manager.update_status(
                    billing_uuid, 
                    BillingStatus.TO_DELETE, 
                    service_type="matcher", 
                    service_sub_type="vm", 
                    payload=to_destroy
                )

                if res is not None:
                    return JSONResponse(status_code=202, content={"status": "to_delete", "billing_uuid": billing_uuid})

            except Exception as e:
                logging.error(e)
                if billing_uuid:
                    billing_manager.update_status(billing_uuid, BillingStatus.ERROR)
                return ElementoInternalServerError(
                    origin="MESON",
                    error=f"Delete failed: {e}",
                    trace=traceback.format_exc(),
                    meson_source="route_delete_compute()",
                )

    except Exception as error:
        logging.error(str(error))
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="route_delete_compute()",
        )

@app.get("/api/v1.0/credentials/{vm_uuid}")
@elemento_iam.validate_request
async def route_get_credentials(request: Request, vm_uuid: str, token: Any = None):
    try:
        client_uuid = str(uuid.UUID(str(getattr(token, "client_uuid"))))

        try:
            creds_response, status_code = get_credentials(client_uuid, vm_uuid)
        except Exception:
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during key rotation for {vm_uuid}",
                trace=traceback.format_exc(),
                meson_source="route_get_credentials()",
            )

        if status_code in [200, 201]:
            file_stream = io.StringIO(creds_response)

            return StreamingResponse(
                iter([file_stream.getvalue()]),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=credentials_{vm_uuid}.txt"},
            )
        elif status_code == 400:
            return ElementoBadRequest(
                origin="PROVIDER",
                error=creds_response.get("error", f"vm in creation: {vm_uuid}"),
                field_errors=[],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="get_credentials()",
            )
        elif status_code in [403, 404]:
            return ElementoNotFound(
                origin="PROVIDER",
                error=f"vm not found: {vm_uuid}",
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


##!####### OLD ENDPOINTS - NOT TESTED ##########
@app.post("/api/v1.0/start")
@elemento_iam.validate_request
async def route_start_compute(request: Request, token: Any = None):
    try:
        to_start = await request.json()
        region = get_from_dict(to_start, "region", None)
        vm_uuid = get_from_dict(to_start, "vm_uuid")
        client_uuid = str(uuid.UUID(str(getattr(token, "client_uuid"))))

        try:
            start_compute(client_uuid, vm_uuid, region)
        except Exception as error:
            logging.error("route_start_compute -", error.__str__())
            return ElementoNotFound(
                origin="MESON",
                error=f"Not found - {error.__str__()}",
                trace=traceback.format_exc(),
                meson_source="route_start_compute()",
            )

        return JSONResponse(status_code=202, content={"success": f"Starting VM {vm_uuid}"})

    except requests.HTTPError as http_err:
        logging.error("route_start_compute -", http_err.__str__())
        return ElementoTooEarly(
            origin="MESON",
            error=f"Too early - {http_err.__str__()}",
            trace=traceback.format_exc(),
            meson_source="route_start_compute()",
        )

    except Exception as error:
        logging.error("route_start_compute -", error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="route_start_compute()",
        )


@app.post("/api/v1.0/stop")
@elemento_iam.validate_request
async def route_stop_compute(request: Request, token: Any = None):
    try:
        to_stop = await request.json()
        region = get_from_dict(to_stop, "region", None)
        vm_uuid = get_from_dict(to_stop, "vm_uuid")
        client_uuid = str(uuid.UUID(str(getattr(token, "client_uuid"))))

        try:
            stop_compute(client_uuid, vm_uuid, region)
        except Exception as error:
            logging.error("route_stop_compute -", error.__str__())
            return ElementoNotFound(
                origin="MESON",
                error=f"Not found - {error.__str__()}",
                trace=traceback.format_exc(),
                meson_source="route_stop_compute()",
            )

        return JSONResponse(status_code=202, content={"success": f"Stopping VM {vm_uuid}"})

    except requests.HTTPError as http_err:
        logging.error("route_stop_compute -", http_err.__str__())
        return ElementoTooEarly(
            origin="MESON",
            error=f"Too early - {http_err.__str__()}",
            trace=traceback.format_exc(),
            meson_source="route_stop_compute()",
        )

    except Exception as error:
        logging.error("route_stop_compute -", error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="route_stop_compute()",
        )


@app.post("/api/v1.0/restart")
@elemento_iam.validate_request
async def route_restart_compute(request: Request, token: Any = None):
    try:
        to_start = await request.json()
        region = get_from_dict(to_start, "region", None)
        vm_uuid = get_from_dict(to_start, "vm_uuid")
        client_uuid = str(uuid.UUID(str(getattr(token, "client_uuid"))))

        try:
            restart_compute(client_uuid, vm_uuid, region)
        except Exception as error:
            logging.error("route_restart_compute -", error.__str__())
            return ElementoNotFound(
                origin="MESON",
                error=f"Not found - {error.__str__()}",
                trace=traceback.format_exc(),
                meson_source="route_restart_compute()",
            )

        return JSONResponse(status_code=202, content={"success": f"Restarting VM {vm_uuid}"})

    except requests.HTTPError as http_err:
        logging.error("route_restart_compute -", http_err.__str__())
        return ElementoTooEarly(
            origin="MESON",
            error=f"Too early - {http_err.__str__()}",
            trace=traceback.format_exc(),
            meson_source="route_restart_compute()",
        )

    except Exception as error:
        logging.error("route_restart_compute -", error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="route_restart_compute()",
        )


@app.get("/api/v1.0/metrics")
@elemento_iam.validate_request
async def route_metrics(request: Request, token: Any = None):
    try:
        try:
            client_uuid = str(uuid.UUID(str(getattr(token, "client_uuid"))))
        except Exception:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="client_uuid",
                        where="BODY",
                        error="WRONG_VALUE",
                        type="str",
                        expected_value="550e8400-e29b-41d4-a716-446655440000",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="route_metrics()",
            )
        servers_dict = get_compute_metrics(client_uuid)

        return JSONResponse(
            status_code=200,
            content={"provider": os.getenv("PROVIDER"), "vms": servers_dict},
        )
    except Exception:
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="route_metrics()",
        )


@app.get("/api/v1.0/metrics/{vm_uuid}")
@elemento_iam.validate_request
async def route_metrics_single(request: Request, vm_uuid: str, token: Any = None):
    try:
        try:
            client_uuid = str(uuid.UUID(str(getattr(token, "client_uuid"))))
        except Exception:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="client_uuid",
                        where="BODY",
                        error="WRONG_VALUE",
                        type="str",
                        expected_value="550e8400-e29b-41d4-a716-446655440000",
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="route_metrics_single()",
            )
        server_info = get_compute_metrics(client_uuid, vm_uuid)

        if server_info is None:
            return ElementoNotFound(
                origin="MESON",
                error="Error during retrieve machine metrics",
                trace=traceback.format_exc(),
                meson_source="route_metrics_single()",
            )
        return JSONResponse(
            status_code=200,
            content={"provider": os.getenv("PROVIDER"), "vms": server_info},
        )

    except Exception:
        return ElementoInternalServerError(
            origin="MESON",
            error="Internal Server Error",
            trace=traceback.format_exc(),
            meson_source="route_metrics_single()",
        )
