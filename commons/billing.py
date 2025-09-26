import logging
import requests
import os
from commons.utils import get_from_dict

# TODO: redo the logic

#! ---------- DEV MODE ----------
if os.getenv("PORTAL_DEV_MODE"):
    PORTAL_URL = os.getenv("ELEMENTO_DEV_PORTAL")
    logging.warning("PORTAL ON DEV MODE")
else:
    PORTAL_URL = os.getenv("ELEMENTO_PORTAL")
#! -------------------------------


# Athentication into the billing portal
def auth_billing():
    try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "authz_account_entity": os.getenv("ELEMENTO_ACCOUNT_ENTITY"),
            "password": os.getenv("ELEMENTO_ACCOUNT_PASSWORD"),
        }
    except ValueError as error:
        logging.error(f"auth_billing - {error.__str__()}")
        raise Exception(f"auth_billing - {error.__str__()}")
    try:
        with requests.post(
            PORTAL_URL + "/auth/userpass", headers=headers, json=payload
        ) as r:
            if r.status_code == 200:
                result = r.json()
                return result["authz_token"]
            else:
                raise Exception(f"portal error - {r.text}")
    except Exception as error:
        logging.error(f"auth_billing - {error.__str__()}")
        raise Exception(f"auth_billing - {error.__str__()}")


# Creates and starts a billing entity into the pricing service
def add_billing_details(target_entity: str, price_json: dict, specs_json: dict, reseller_id: str) -> str:
    try:
        authz_token = auth_billing()
        try:
            payload = {
                "authz_account_entity": os.getenv("ELEMENTO_ACCOUNT_ENTITY"),
                "authz_token": authz_token,
                "target_entity": os.getenv("ELEMENTO_ACCOUNT_TARGET"),
                "reseller_id": reseller_id,
                "price": price_json,
                "specs": specs_json,
                "provider": os.getenv("PROVIDER"),
                "status": "billed",
                "start_timestamp": 0,
                "end_timestamp": 0,
            }
        except ValueError as error:
            logging.error(f"add_billing_details - {error.__str__()}")
            raise Exception(f"add_billing_details - {error.__str__()}")
        with requests.post(PORTAL_URL + "/billing/add", json=payload) as r:
            if r.status_code == 200:
                result = r.json()
                logging.info("Billing started")
                return result["billing_uuid"]
            else:
                raise Exception(f"portal error - {r.text}")
    except Exception as error:
        logging.error(f"add_billing_details - {error.__str__()}")
        raise Exception(f"add_billing_details - {error.__str__()}")


# Calls the billing service for updating (or stopping) the status for a given service
def update_billing_details(billing_uuid: str, status: str, reseller_id: str):
    try:
        authz_token = auth_billing()
        try:
            headers = {"Content-Type": "application/json"}
            payload = {
                "authz_account_entity": os.getenv("ELEMENTO_ACCOUNT_ENTITY"),
                "authz_token": authz_token,
                "target_entity": os.getenv("ELEMENTO_ACCOUNT_TARGET"),
                "reseller_id": reseller_id,
                "billing_entry_id": billing_uuid,
                "status": status,
            }
        except ValueError as error:
            logging.error(f"update_billing_details - {error.__str__()}")
            raise Exception("ENV variables not set in billing")
        with requests.post(
            PORTAL_URL + "/billing/update/status", headers=headers, json=payload
        ) as r:
            result = r.json()
        if r.status_code == 200:
            logging.info("Billing status updated")
            return result
        else:
            raise Exception("Error in billing creation")
    except Exception as error:
        logging.error(f"update_billing_details - {error.__str__()}")
        raise Exception(f"update_billing_details - {error.__str__()}")


def get_pricing(config) -> dict:
    try:
        if os.getenv("PORTAL_DEV_MODE"):  ##! TMP
            pricing = {
                "currency": "EUR",
                "monthly": 30,
                "hourly": 1,
            }
            config.update({"price": pricing})
            return pricing

        URL = "https://prices.portal.elemento.cloud"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv("ELEMENTO_ACCOUNT_TOKEN")}",
        }
        payload = {
            "data": config,
            "mesos": {
                "provider": os.getenv(provider.lower()),
                "region": os.getenv(provider_region.lower()),
            },
        }

        with requests.post(URL + "/api/v1/price", headers=headers, json=payload) as r:
            if r.status_code < 200 or r.status_code >= 300:
                raise Exception(
                    f"get_pricing: error in retrieve pricing - status code {r.status_code} from Portal"
                )
            price = r.json()

        meson_pricing = get_from_dict(price, "mesos")
        pricing = {
            "currency": get_from_dict(meson_pricing, "price", "unit"),
            "monthly": int(get_from_dict(meson_pricing, "price", "month")),
            "hourly": int(get_from_dict(meson_pricing, "price", "hour")),
        }

        config.update({"price": pricing})
        return pricing
    except ValueError as error:
        logging.error(f"get_pricing - {error.__str__()}")
        raise Exception(f"get_pricing: error in retrieve pricing - {error.__str__()}")