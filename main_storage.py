import logging
import os
import traceback
from typing import Any
import httpx

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from __init__ import __version__
from commons.elemento_iam import ElementoIdentityAccessManagement
from elemento_billing_manager.billing_manager import BillingStatus, billing_manager
from errors.client_errors import ElementoBadRequest, ElementoNotFound
from errors.server_errors import ElementoCreationFailed, ElementoInternalServerError
from infrastructure.storage.storage_manager import (
    create_storage,
    delete_storage,
    list_storage,
    get_storage_by_uuid,
    is_storage_config_available,
)
from models.StorageModel import Storage
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
    def filter(self, record):
        msg = record.getMessage()
        return not any(path in msg for path in ["GET /api/v1.0/health", "GET / HTTP/1.1"])

uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(HealthCheckFilter())


@app.get("/")
async def root(token: Any = None):
    return PlainTextResponse(
        status_code=200,
        content=f"Hello, world! This is an Elemento Storage Meson for provider {os.getenv('PROVIDER', 'gcp')}.",
    )


@app.get("/api/v1.0/health")
def health(token: Any = None):
    # TODO: perform a GET request and check the response to ensure the provider is healthy
    return JSONResponse(
        status_code=200,
        content={"status": "UP", "version": __version__, "provider_status": "TODO"},
    )


@app.post("/api/v1.0/info")
@elemento_iam.validate_request
async def route_get_storage_by_uuid(request: Request, token: Any = None):
    try:
        info = await request.json()
        volume_uuid = info['volume_id']
        response = get_storage_by_uuid(volume_uuid)
        if response is None:
            return ElementoNotFound(
                origin="MESON",
                error="Volume not found",
                trace=traceback.format_exc(),
            )
        return JSONResponse(content=response.to_json_response(), status_code=200)
    except Exception as ex:
        logging.error(ex.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {ex}",
            trace=traceback.format_exc(),
        )


@app.post("/api/v1.0/accessible")
@elemento_iam.validate_request
async def route_list_storage(request: Request, token: Any = None):
    try:
        accessible_json = await request.json()
        client_uuid = accessible_json["client_uid"]
    except Exception as ex:
        logging.error(ex.__str__())
        return ElementoBadRequest(
            origin="MESON",
            error=f"Bad Request - {ex}",
            field_errors=[],
            docs_url="",
            trace=f"{traceback.format_exc()}",
            meson_source="route_list_storage()",
        )
    try:
        response = list_storage(client_uuid)
        if len(response) == 0:
            return ElementoNotFound(
                origin="MESON",
                error="Volume not found",
                trace=traceback.format_exc(),
            )
        volumes_out = [volume.to_json_response() for volume in response]
        return JSONResponse(content=volumes_out, status_code=200)
    except Exception as ex:
        logging.error(ex.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {ex}",
            trace=traceback.format_exc(),
        )


@app.get("/api/v1.0/cancreate")
@elemento_iam.validate_request
async def route_cancreate_storage(request: Request, token: Any = None):
    config = await request.json()
    try:
        size = config["size"]
    except Exception as ex:
        logging.error(ex.__str__())
        return ElementoBadRequest(
            origin="MESON",
            error=f"Bad Request - {ex}",
            field_errors=[],
            docs_url="",
            trace=f"{traceback.format_exc()}",
            meson_source="route_cancreate_storage()",
        )

    is_available = is_storage_config_available(int(size))
    
    if is_available is True:
        return JSONResponse(content=config, status_code=200)
    else:
        return JSONResponse(content={'data': 'creation not available'}, status_code=400)


@app.post("/api/v1.0/create")
@elemento_iam.validate_request
async def route_create_storage(request: Request, token: Any = None):
    create_json = await request.json()

    interval = "month"
    org = token.elemento_org
    client_uuid = token.client_uuid
    role = token.elemento_role.lower()

    billing_uuid = create_json.get("billing_uuid", None)
    parent_billing_uuid = create_json.get("parent_billing_uuid", None)

    try:
        if "creatorID" not in create_json and "creator_id" in create_json:
            create_json["creatorID"] = create_json["creator_id"]
        if "volumeID" not in create_json and "volume_uuid" in create_json:
            create_json["volumeID"] = create_json["volume_uuid"]

        storage_data = Storage.from_json(create_json)
        storage_data.creator_id = create_json.get("creatorID", client_uuid)
        
        resolved_zone = (
            create_json.get("region") or 
            create_json.get("csp_region") or 
            create_json.get("zone") or 
            os.environ.get("PROVIDER_REGION")
        )
        
        storage_data.region = resolved_zone
        storage_data.csp_region = resolved_zone
            
    except Exception as ex:
        logging.error(ex.__str__())
        return ElementoBadRequest(
            origin="MESON",
            error=f"Bad Request - {ex}",
            field_errors=[],
            docs_url="",
            trace=traceback.format_exc(),
            meson_source="route_create_storage()",
        )

    try:
        if not billing_uuid:
            try:
                if parent_billing_uuid:
                    billing_uuid = billing_manager.start_sub(
                        client_uuid=storage_data.creator_id,
                        parent_billing_uuid=parent_billing_uuid,
                        payload=create_json,
                        org=org,
                        service_type="storage",
                        service_sub_type="blockstorage",
                        region=storage_data.region,
                        provider=os.getenv("PROVIDER", "gcp"),
                    )
                else:
                    payment_link, billing_uuid = billing_manager.start(
                        client_uuid=storage_data.creator_id,
                        payload=create_json,
                        service_type="storage",
                        service_sub_type="blockstorage",
                        region=storage_data.region,
                        provider=os.getenv("PROVIDER", "gcp"),
                        org=org,
                        interval=interval,
                    )
                    return JSONResponse(status_code=202, content={"payment_url": payment_link, "billing_uuid": str(billing_uuid)})
            except Exception as e:
                logging.error(f"Error: {str(e)}")
                return JSONResponse(status_code=500, content={"error": "billing_failed", "details": str(e)})

        if role == 'portal' or billing_uuid:
            storage_data.billing_uuid = billing_uuid
            
            if resolved_zone:
                storage_data.region = resolved_zone
                storage_data.csp_region = resolved_zone
            
            billing_manager.update_status(billing_uuid, BillingStatus.PROVISIONING)
            disk_name = create_storage(storage_data)
            billing_manager.update_status(billing_uuid, BillingStatus.RUNNING)
            storage_data.name = disk_name
            
            return JSONResponse(content=storage_data.to_json_response(), status_code=200)

    except Exception as ex:
        if billing_uuid:
            billing_manager.update_status(billing_uuid, BillingStatus.ERROR)
        logging.error(f"Error during storage creation: {ex.__str__()}")
        return ElementoCreationFailed(
            origin="MESON",
            error=f"Error during storage creation - {ex.__str__()}",
            trace=traceback.format_exc(),
            stopped_successfully=True,
            billing_suspended=True,
            meson_source="route_create_storage()",
        )


@app.post("/api/v1.0/destroy")
@elemento_iam.validate_request
async def route_delete_storage(request: Request, token: Any = None):
    try:
        role = token.elemento_role.lower()
        client_uuid = token.client_uuid
        to_destroy = await request.json()
        
        try:
            volume_id = to_destroy["volume_id"]
        except Exception as ex:
            return ElementoBadRequest(
                origin="MESON",
                error=f"Bad Request - Missing volume_id: {ex}",
                field_errors=[],
                docs_url="",
                trace=f"{traceback.format_exc()}",
                meson_source="route_delete_storage()",
            )
            
        try:
            volume = get_storage_by_uuid(volume_id)
        except Exception as e:
            volume = None
            logging.debug(f"Volume lookup notice: {str(e)}")

        if not volume:
            return ElementoNotFound(
                origin="MESON", 
                error="Volume not found on GCP infrastructure. Cannot proceed."
            )

        billing_uuid = volume.billing_uuid
        
        if not billing_uuid:
            return ElementoNotFound(
                origin="MESON", 
                error="Billing UUID not found for this volume"
            )

        if role == 'portal' and to_destroy.get("client_uuid"):
            try:
                isDeleted = delete_storage(volume_id)
                
                if isDeleted:
                    billing_manager.update_status(billing_uuid, BillingStatus.DELETED)
                    return JSONResponse(content={"destroyed": True, "vid": volume_id}, status_code=200)
                else:
                    billing_manager.update_status(billing_uuid, BillingStatus.ERROR)
                    return ElementoNotFound(
                        origin="MESON",
                        error="Volume not found or could not be deleted synchronously on GCP",
                        trace=traceback.format_exc(),
                    )
            except Exception as ex:
                billing_manager.update_status(billing_uuid, BillingStatus.ERROR)
                logging.error(str(ex))
                return ElementoInternalServerError(
                    origin="MESON",
                    error=f"Internal Server Error during synchronous portal deletion - {ex}",
                    trace=f"{traceback.format_exc()}",
                )

        else:
            try:
                to_destroy['client_uuid'] = to_destroy.get('client_uid', client_uuid)
                res = billing_manager.update_status(
                    billing_uuid, 
                    BillingStatus.TO_DELETE, 
                    service_type="storage", 
                    service_sub_type="blockstorage",
                    payload=to_destroy
                )
                if res is not None:
                    return JSONResponse(status_code=202, content={"status": "to_delete", "billing_uuid": billing_uuid})
            except Exception as ex:
                return ElementoBadRequest(
                    origin="MESON",
                    error=f"Volume tracking error for standard user - {ex}",
                    field_errors=[],
                    docs_url="",
                    trace=f"{traceback.format_exc()}",
                    meson_source="route_delete_storage()",
                )
    except Exception as e:
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Fatal Error - {e}",
            trace=f"{traceback.format_exc()}",
        )