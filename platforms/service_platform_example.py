from models.PlatformExampleModel import ExampleModel, ExampleCapabilities

# This file contains the functions that will be used to execute specific services on this specific provider.

def get_service(service_uuid: str, client_uuid: str, service_credentials: str = None, service_country: str = None) -> tuple:
    """
    Retrieve a specific service form the provider.
    Args:
        service_uuid (str): The service UUID to retrieve
        client_uuid (str): The client UUID
        service_country (str): optional, region to use
    Returns:
        tuple: (The service configuration if found, status_code)
    Raises:
        Exception: If service is not found or other errors occur
    """
    try:
        service_config = {}
        # Add code in order to return the service based on service id

        return service_config, 200

    except Exception as e:
        return {"error": f"Error in retrieve service configs - {e}"}, 500


def get_all_services(client_uuid: str, service_credentials: str = None, service_country: str = None) -> tuple:
    """
    Retrieve all the services from the provider.
    Args:
        client_uuid (str): client to retrieve provided services.
        service_country (str): optional, region to use
    Returns:
        tuple: (The response data with the services, status_code)
    """
    try:
        list_service_configs = []
        # Add code in order to return a list of services based on client_uuid

        return list_service_configs, 200

    except Exception as e:
        return {"error": f"Error in retrieve global configs - {e}"}, 500


def is_config_available(service_config: ExampleModel, service_country: str) -> bool:
    """
    Checks if the provided service_config is compatible with the provider offering.
    """
    return True


def setup_config(req_data: dict, client_uuid: str, billing_uuid: str, service_country: str) -> ExampleModel:
    """
    Create a new service instance from JSON request.
    Args:
        req_data (dict): requested provider config
        client_uuid (str): client_uuid to be assigned
        billing_uuid (str): billing identifier
        service_country (str): region to use
    Returns:
        ExampleModel: new instance of service
    """
    try:
        # Preliminary operations
        req_metadata = {}
        req_resources = {}
        capabilities = ExampleCapabilities()

        return ExampleModel(req_metadata, req_resources, client_uuid, billing_uuid, capabilities)

    except KeyError as e:
        raise Exception(e)


def create(service_config: ExampleModel, service_credentials: str = None, service_country: str = None) -> tuple:
    """
    Create a new service.
    Args:
        service_config (ExampleModel): The service configuration data model.
        service_country (str): optional, region to use.
    Returns:
        tuple: (The response data with the created service, status_code)
    """
    try:
        if not is_config_available(service_config, service_country):
            return {"error": "Service configuration is not available"}, 400

        ##! NOTE: the billing id must be attach as a entry of the dict
        # It is already in the service config as field
        # Insert here the POST to create service

        return service_config, 200

    except KeyError as e:
        return {"error": f"Error in service creation - {e}"}, 500


def delete(service_id: str, client_uuid: str, service_credentials: str = None, service_country: str = None) -> tuple:
    """
    Delete a service in the provider.
    Args:
        service_id (str): The service id to delete.
        client_uuid (str): Client indetifier.
        service_country (str): optional, region to use.
    Returns:
        tuple: (billing_uuid, status_code)
    """
    try:
        # Delete the resource
        billing_uuid = "af490b1a-c597-4d65-85a0-38aced0b3e4f" # Example
        return billing_uuid, 200
    
    except Exception as e:
        return {"error": f"Error in service deletion - {e}"}, 500


# ------------------------ UTILS FUNCTIONS ------------------------

# Insert here optional utils functions needed to perform the tasks above