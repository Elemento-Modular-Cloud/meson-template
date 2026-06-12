# NOTE: All the software services file names must start with "service_" in order to be dynamically imported by the main service file.

from models.PlatformExampleModel import ExampleModel, ExampleCapabilities

# This file contains the functions that will be used to execute specific services on this specific provider.

def get_service(service_uuid: str, client_uuid: str) -> tuple:
    """
    Retrieve a specific service form the provider.
    Args:
        service_uuid (str): The service UUID to retrieve
        client_uuid (str): The client UUID
    Returns:
        tuple: (The service configuration if found, status_code)
    Raises:
        Exception: If service is not found or other errors occur
    """
    try:
        service_config = {}
        # Add code in order to return the service based on client_uuid and service_uuid

        return service_config, 200

    except Exception as e:
        return {"error": f"Error in retrieve service configs - {e}"}, 500


def get_all_services(client_uuid: str) -> tuple:
    """
    Retrieve all the services from the provider.
    Args:
        client_uuid (str): client to retrieve provided services.
    Returns:
        tuple: (The response data with the services, status_code)
    """
    try:
        list_service_configs = []
        # Add code in order to return a list of services based on client_uuid

        return list_service_configs, 200

    except Exception as e:
        return {"error": f"Error in retrieve global configs - {e}"}, 500


def setup_config(req_data: dict, client_uuid: str) -> ExampleModel:
    """
    Create a new service instance from JSON request.
    Args:
        req_data (dict): requested provider config
        client_uuid (str): client_uuid to be assigned
    Returns:
        ExampleModel: new instance of service
    """
    try:
        # Add code in order to create a new instance of the service configuration model based on the request data. The client_uuid must be assigned to the new service instance.
        req_metadata = {}
        req_resources = {}
        capabilities = ExampleCapabilities()

        return ExampleModel(req_metadata, req_resources, client_uuid, capabilities)

    except KeyError as e:
        raise Exception(e)


def create(service_config: ExampleModel) -> tuple:
    """
    Create a new service.
    Args:
        service_config (ExampleModel): The service configuration data model.
    Returns:
        tuple: (The response data with the created service, status_code)
    """
    try:
        
        ##! NOTE: the billing_uuid and client_uuid must be inserted inside a field of the service (ex: labels, tags, names, etc) 
        ##! in order to be able to retrieve it in the future when the service is deleted.

        # Insert here the POST to create service

        return service_config, 200

    except KeyError as e:
        return {"error": f"Error in service creation - {e}"}, 500


def delete(service_id: str, client_uuid: str) -> tuple:
    """
    Delete a service in the provider.
    Args:
        service_id (str): The service id to delete.
        client_uuid (str): Client indetifier.
    Returns:
        tuple: (billing_uuid, status_code)
    """
    try:
        # Delete the resource
        billing_uuid = "af490b1a-c597-4d65-85a0-38aced0b3e4f" # Example
        return billing_uuid, 200
    
    except Exception as e:
        return {"error": f"Error in service deletion - {e}"}, 500
    

def cancreate(service_config: ExampleModel) -> bool:
    """
    Checks if the provided service_config can be created with the provider offering.
    Args:
        service_config (ExampleModel): The service configuration data model.
    Returns:
        bool: True if the service can be created, False otherwise.
    """
    try:
        return True
    
    except Exception as e:
        print(f"Error occurred while checking if service can be created: {e}")
        return False


def get_credentials(service_id: str, client_uuid: str) -> tuple:
    """
    Retrieve the credentials of a service.
    Args:
        service_id (str): The service id to retrieve credentials.
        client_uuid (str): Client indetifier.
    Returns:
        tuple: (The response data with the credentials, status_code)
    """
    try:
        credentials = {}
        # Insert here the code to retrieve the credentials of the service

        return credentials, 200
    
    except Exception as e:
        return {"error": f"Error in retrieve credentials - {e}"}, 500


# ------------------------ UTILS FUNCTIONS ------------------------

# Insert here optional utils functions needed to perform the tasks above