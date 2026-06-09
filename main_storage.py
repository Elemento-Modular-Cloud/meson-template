import logging
import traceback
import uuid
import os

from __init__ import __version__
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from commons.utils import check_storage_params, check_storage_tolerance, get_from_dict
from models.StorageModel import ElementoStorage
from infrastructure.storage.storage_manager import (
    information_about_storages_by_id,
    information_about_storages_by_client_id,
    is_storage_available,
    create_storage,
    destroy_storage,
)
from errors.client_errors import (
    ElementoBadRequest,
    ElementoNotFound,
    ElementoTooEarly,
    BadRequestFieldError
)
from errors.server_errors import (
    ElementoBillingFailed,
    ElementoCreationFailed,
    ElementoInternalServerError,
    ElementoServiceUnavailable
)
from commons.elemento_iam import ElementoIdentityAccessManagement
from elemento_billing_manager.billing_manager import billing_manager
from dotenv import load_dotenv
from elogger.logger_manager_fastapi import setup_logging
from asgi_correlation_id import CorrelationIdMiddleware

load_dotenv()

elemento_iam = ElementoIdentityAccessManagement()
app = FastAPI()
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
    PlainTextResponse(
        status_code=200,
        content=f"Hello, world! This is an Elemento Storage Meson for provider {os.getenv('PROVIDER')}",
    )


@app.get("/api/v1.0/health")
def health():
    return JSONResponse(
        status_code=200,
        content={"status": "UP", "version": __version__},
    )


@app.get("/api/v1.0/info")
@elemento_iam.validate_request
async def storages_description(req: Request):
    try:
        info = await req.json()
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        try:
            volume_uuid = get_from_dict(info, "volume_uuid")
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad request - bad payload",
                field_errors=[
                    BadRequestFieldError(
                        field="volume_uuid",
                        where="BODY",
                        error="MISSING",
                        type="UUID",
                        expected_value=""
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="storage_accessible()"
            )

        response = information_about_storages_by_id(volume_uuid, service_country)
        return JSONResponse(response.to_json_response(), status_code=200)

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="storage_destruction()"
        )

@app.get("/api/v1.0/info/{volume_uuid}")
@elemento_iam.validate_request
async def server_description_by_id(req: Request, volume_uuid: str):
    try:
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        response = information_about_storages_by_id(volume_uuid=volume_uuid, service_country=service_country)

        return JSONResponse(
            status_code=200, content=response.to_json_response()
        )

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            meson_source="server_description_by_id()",
            trace=traceback.format_exc()
        )

@app.get("/api/v1.0/accessible")
@elemento_iam.validate_request
async def storage_accessible(req: Request):
    try:
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        try:
            client_uuid = req.query_params.get("client_uuid")
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad request - bad payload",
                field_errors=[
                    BadRequestFieldError(
                        field="client_uuid",
                        where="QUERY",
                        error="MISSING",
                        type="UUID",
                        expected_value=""
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="storage_accessible()"
            )

        client_volumes = information_about_storages_by_client_id(client_uuid, service_country)
        response = []
        for volume in client_volumes:
            response.append(volume.to_json_response())
        return JSONResponse(response, status_code=200)

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="storage_destruction()"
        )


@app.post("/api/v1.0/create")
@elemento_iam.validate_request
async def storage_creation(req: Request):
    billing_uuid = None
    client_uuid = None
    try:
        storages_to_create = await req.json()
        async_flag = "false"
        if req.headers.get("Async") is not None:
            async_flag = req.headers.get("Async")
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        try:
            storage_data = ElementoStorage(
                csp_region=service_country,
                creator_id=get_from_dict(storages_to_create, "creatorID"),
                name=get_from_dict(storages_to_create, "name"),
                size=get_from_dict(storages_to_create, "size"),
                private=storages_to_create.get("private"),
                readonly=storages_to_create.get("readonly"),
                shareable=storages_to_create.get("shareable"),
                bootable=storages_to_create.get("bootable"),
            )
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad request - bad payload",
                field_errors=[],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="storage_creation()"
            )

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
            billing_uuid = billing_manager.start(client_uuid, specs, "storage", "objectstorage", None)
            # -------------------
            storage = create_storage(storage_data, service_country, billing_uuid)
            if not check_storage_params(storage):
                raise Exception(
                    "Some mandatory Storage params are missing (volume_uuid, billing_uuid, creator_id, name, size)"
                )
            return JSONResponse(content=storage.to_json_response(), status_code=200)
        except Exception as error:
            # -- STOP BILLING --
            billing_manager.stop(billing_uuid, client_uuid)
            # ------------------
            logging.error(f"Error during storage creation: {error.__str__()}")
            return ElementoCreationFailed(
                origin="MESON",
                error="Error during storage creation",
                trace=traceback.format_exc(),
                stopped_successfully=True,
                billing_suspended=True,
                meson_source="storage_creation()"
            )

    except Exception as error:
        # -- STOP BILLING --
        billing_manager.stop(billing_uuid, client_uuid)
        # ------------------    
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="storage_creation()"
        )


@app.get("/api/v1.0/cancreate")
@elemento_iam.validate_request
async def storage_cancreate(req: Request):
    try:
        storages_to_create = await req.json()
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        try:
            storage_data = ElementoStorage(
                csp_region=service_country,
                size=get_from_dict(storages_to_create, "size"),
                private=storages_to_create.get("private"),
                readonly=storages_to_create.get("readonly"),
                shareable=storages_to_create.get("shareable"),
                bootable=storages_to_create.get("bootable"),
            )
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad request - bad payload",
                field_errors=[],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="storage_cancreate()"
            )
        storage_config = is_storage_available(storage_data, service_country)
        if storage_config is None or not check_storage_tolerance(
            requested=storage_data, proposed=storage_config
        ):
            return ElementoCreationFailed(
                origin="MESON",
                error="Config is not available",
                trace=traceback.format_exc(),
                stopped_successfully=True,
                billing_suspended=True,
                meson_source="storage_cancreate()",
            )

        return JSONResponse(content=None, status_code=200)

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="storage_cancreate()"
        )


@app.delete("/api/v1.0/destroy")
@elemento_iam.validate_request
async def storage_destruction(req: Request):
    billing_uuid = None
    try:
        to_destroy = await req.json()
        service_country = req.headers["service_country"] if "service_country" in req.headers.keys() else os.getenv("PROVIDER_REGION")
        try:
            volume_uuid = get_from_dict(to_destroy, "volume_uuid")
        except Exception as error:
            return ElementoBadRequest(
                origin="MESON",
                error="Bad Request",
                field_errors=[
                    BadRequestFieldError(
                        field="volume_uuid",
                        where="BODY",
                        error="MISSING",
                        type="UUID",
                        expected_value=""
                    )
                ],
                docs_url="",
                trace=traceback.format_exc(),
                meson_source="storage_destruction()"
            )

        try:
            storage_config = information_about_storages_by_id(volume_uuid, service_country)
        except Exception as error:
            return ElementoNotFound(
                origin="MESON",
                error="Error during storage retrieve information",
                trace=traceback.format_exc(),
                meson_source="storage_destruction()"
            )

        try:
            response = destroy_storage(volume_uuid, service_country)
        except Exception as error:
            return ElementoInternalServerError(
                origin="MESON",
                error=f"Error during storage destruction - {error.__str__()}",
                trace=traceback.format_exc(),
                meson_source="storage_destruction"
            )

        try:
            # -- STOP BILLING --
            billing_manager.stop(storage_config.billing_uuid, client_uuid)
            # ------------------
        except Exception as error:
            return ElementoBillingFailed(
                origin="MESON",
                error="Error during billing suspension",
                trace=traceback.format_exc(),
                stopped_successfully=True,
                meson_source="storage_destruction()"
            )

        return JSONResponse(
            content={"unregistered": response, "uniqueID": volume_uuid}, status_code=200
        )

    except Exception as error:
        logging.error(error.__str__())
        return ElementoInternalServerError(
            origin="MESON",
            error=f"Internal Server Error - {error.__str__()}",
            trace=traceback.format_exc(),
            meson_source="storage_destruction()"
        )
