from typing import List

class SaaSExampleLabels:
    
    def __init__(
        self,
        provider_id,
        client_uuid,
    ):
        self.provider_id = provider_id
        self.client_uuid = client_uuid

    def to_json(self):
        try:
            return {
                "id": self.provider_id,
                "client_uuid": self.client_uuid
            }
        except Exception as e:
            raise Exception(f"Cannot create JSON (SaaSExampleLabels) {e.__str__()}")

class SaaSExampleCapabilities:
    
    def __init__(
        self,
        framework_id,
        framework_version
    ):
        self.framework_id = framework_id
        self.framework_version = framework_version

    def to_json(self):
        try:
            return {
                "framework_id": self.framework_id,
                "framework_version": self.framework_version
            }
        except Exception as e:
            raise Exception(f"Cannot create JSON (SaaSExampleCapabilities) {e.__str__()}")

class SaaSExampleUrls:
    
    def __init__(
        self,
        url,
        info_url,
        monitoring_url,
        ssh_url,
    ):
        self.url = url
        self.info_url = info_url
        self.monitoring_url = monitoring_url
        self.ssh_url = ssh_url

    def to_json(self):
        try:
            return {
                "url": self.url,
                "info_url": self.info_url,
                "monitoring_url": self.monitoring_url,
                "ssh_url": self.ssh_url
            }
        except Exception as e:
            raise Exception(f"Cannot create JSON (SaaSExampleUrls) {e.__str__()}")

class SaaSExampleMetadata:
    
    def __init__(
        self,
        id: str = None,
        name: str = None,
        user: str = None,
        state: str = None,
        region: str = None,
        updated_at: str = None,
        labels: SaaSExampleLabels = None,
        saas_example_env_vars: List = [],
        urls: SaaSExampleUrls = None
    ):
        self.id = id
        self.name = name
        self.user = user
        self.state = state
        self.region = region
        self.updated_at = updated_at
        self.labels = labels
        self.saas_example_env_vars = saas_example_env_vars
        self.urls = urls
    
    def to_json(self):
        try:
            return {
                "id": self.id,
                "name": self.name,
                "user": self.user,
                "state": self.state,
                "region": self.region,
                "updatedAt": self.updated_at,
                "labels": self.labels.to_json(),
                "jupyterEnvVars": self.saas_example_env_vars,
                "credentials": {
                    "username": "username",
                    "password": "password"
                },
                "urls": self.urls.to_json()
            }
        except Exception as ex:
            raise Exception(f"Cannot create JSON (SaaSExampleMetadata): {ex}") 

class SaaSExampleResources:

    def __init__(
        self,
        cpu: int = 0,
        ephemeral_storage: int = 0,
        flavor: str = None,
        gpu: int = 0,
        gpu_brand: str = None,
        gpu_memory: int = 0,
        gpu_model: str = None,
        memory: int = 0,
        private_network: int = 0,
        public_network: int = 0
    ):
        self.cpu = cpu
        self.ephemeral_storage = ephemeral_storage
        self.flavor = flavor
        self.gpu = gpu
        self.gpu_brand = gpu_brand
        self.gpu_memory = gpu_memory
        self.gpu_model = gpu_model
        self.memory = memory
        self.private_network = private_network
        self.public_network = public_network

    def to_json(self):
        try:
            return {
                "cpu": self.cpu,
                "ephemeral_storage": self.ephemeral_storage,
                "flavor": self.flavor,
                "gpu": self.gpu,
                "gpu_brand": self.gpu_brand,
                "gpu_memory": self.gpu_memory,
                "gpu_model": self.gpu_model,
                "memory": self.memory,
                "private_network": self.private_network,
                "public_network": self.public_network
            }
        except Exception as ex:
            raise Exception(f"Cannot create JSON (SaaSExampleResources): {ex}")

class ElementoSaaSExample: 
    def __init__(
        self,
        metadata: SaaSExampleMetadata = None,
        capabilities: SaaSExampleCapabilities = None,
        resources: SaaSExampleResources = None,
    ):
        self.metadata = metadata
        self.capabilities = capabilities
        self.resources = resources

    def to_json(self):
        try:
            return {
                "metadata": self.metadata.to_json(),
                "capabilities": self.capabilities.to_json(),
                "resources": self.resources.to_json(),
            }
        except Exception as ex:
            raise Exception(f"Cannot create JSON (ElementoSaaSExample): {ex}")

class SaaSExampleService:

    def __init__(self):
        pass

    def __build_model(self, service_config) -> ElementoSaaSExample:
        try:
            provider_labels = get_from_dict(service_config, key="spec", key2="labels")
            provider_capabilities = get_from_dict(service_config, key="spec", key2="env")
            provider_status = get_from_dict(service_config, key="status")
            provider_resources = get_from_dict(service_config, key="spec", key2="resources")

            labels = SaaSExampleLabels(
                client_uuid=provider_labels["client_uuid"],
                provider_id=provider_labels["provider_name/id"],
            )

            capabilities = SaaSExampleCapabilities(
                framework_id=provider_capabilities["frameworkId"],
                framework_version=provider_capabilities["frameworkVersion"],
            )

            urls = SaaSExampleUrls(
                url=provider_status["url"],
                info_url=provider_status["infoUrl"],
                monitoring_url=provider_status.get("monitoringUrl", None),
                ssh_url=provider_status.get("sshUrl", None),
            )

            metadata = SaaSExampleMetadata(
                id=service_config["id"],
                name=service_config["spec"]["name"],
                user=service_config["user"],
                state=service_config["status"]["state"],
                region=service_config["spec"]["region"],
                updated_at=service_config["updatedAt"],
                labels=labels,
                capabilities=capabilities,
                saas_example_env_vars=service_config["spec"]["envVars"],
                urls=urls,
            )

            resources = SaaSExampleResources(
                cpu=provider_resources["cpu"],
                ephemeral_storage=provider_resources["ephemeralStorage"],
                flavor=provider_resources["flavor"],
                gpu=provider_resources["gpu"],
                gpu_brand=provider_resources["gpuBrand"],
                gpu_memory=provider_resources["gpuMemory"],
                gpu_model=provider_resources["gpuModel"],
                memory=provider_resources["memory"],
                private_network=provider_resources["privateNetwork"],
                public_network=provider_resources["publicNetwork"],
            )

            return ElementoSaaSExample(
                metadata=metadata, resources=resources
            )

        except Exception as error:
            raise Exception(error)