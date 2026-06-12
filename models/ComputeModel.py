import json
import os
from models.StorageModel import Storage


class CpuModel:

    def __init__(
        self,
        slots: int = 1,
        fullPhysical: bool = True,
        maxOverprovision: int = 1,
        min_frequency: float = 1.0,
        arch: list[str] = None,
        flags: list[str] = None,
    ):
        self.slots = int(slots)
        self.fullPhysical = fullPhysical
        self.maxOverprovision = int(maxOverprovision)
        self.min_frequency = float(min_frequency)
        self.arch = arch
        self.flags = flags

    @staticmethod
    def from_json(json: dict):
        return CpuModel(
            slots=json["slots"] if json["fullPhysical"] is True else json["slots"] / 2,
            fullPhysical=json["fullPhysical"],
            maxOverprovision=json["maxOverprovision"],
            min_frequency=json["min_frequency"],
            arch=json["arch"],
            flags=json["flags"],
        )

    def to_json(self):
        return {
            "slots": self.slots,
            "fullPhysical": self.fullPhysical,
            "maxOverprovision": self.maxOverprovision,
            "min_frequency": self.min_frequency,
            "arch": [arch for arch in self.arch] if self.arch else [],
            "flags": [flag for flag in self.flags] if self.flags else [],
        }


class MemoryModel:

    def __init__(
        self,
        capacity: int = 1024,
        requireECC: bool = False,
    ):
        self.capacity = int(capacity)
        self.requireECC = requireECC

    @staticmethod
    def from_json(json: dict):
        return MemoryModel(
            capacity=int(json["capacity"]),
            requireECC=json["requireECC"],
        )

    def to_json(self):
        return {
            "capacity": self.capacity,
            "requireECC": self.requireECC
        }


class PciDevModel:

    def __init__(
        self,
        vendor: str = None,
        model: str = None,
        quantity: int = 0,
    ):
        self.vendor = vendor
        self.model = model
        self.quantity = int(quantity)

    @staticmethod
    def from_json(key: str, value: int):
        vendor, model = key.split(":")
        return PciDevModel(
            vendor=vendor,
            model=model,
            quantity=int(value),
        )

    def to_json(self):
        return {f"{self.vendor}:{self.model}": self.quantity}


class MiscModel:

    def __init__(
        self,
        os_family: str = None,
        os_flavour: str = None,
    ):
        self.os_family = os_family
        self.os_flavour = os_flavour

    @staticmethod
    def from_json(json: dict):
        return MiscModel(
            os_family=json["os_family"],
            os_flavour=json["os_flavour"],
        )

    def to_json(self):
        return {
            "os_family": self.os_family,
            "os_flavour": self.os_flavour
        }


class NetworkConfigModel:

    def __init__(
        self,
        ipv4: str = None,
        ipv6: str = None,
        mac: str = None,
    ):
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.mac = mac

    def to_json(self):
        return {"ipv4": self.ipv4, "ipv6": self.ipv6, "mac": self.mac}


class AuthModel:

    def __init__(
        self,
        ssh_key: str = None,
        username: str = None,
        password: str = None,
    ):
        self.ssh_key = ssh_key
        self.username = "elemento"
        self.password = "Test.elemento1"
        if username:
            self.username = username.lower()
        if password:
            self.password = password

    @staticmethod
    def from_json(json: dict):
        return AuthModel(
            ssh_key=json["ssh-key"],
            username=json["username"],
            password=json["password"],
        )

    def to_json(self):
        return {
            "ssh-key": self.ssh_key,
            "username": self.username,
            "password": self.password,
        }


class VmModel:

    def __init__(
        self,
        client_uuid: str = None,
        vm_name: str = None,
        volumes: list[Storage] = None,
        billing_uuid: str = None,
        vm_uuid: str = None,
        cpu: CpuModel = CpuModel(),
        mem: MemoryModel = MemoryModel(),
        pci: list[PciDevModel] = list(),
        misc: MiscModel = MiscModel(),
        network_config: NetworkConfigModel = NetworkConfigModel(),
        private_network_config: NetworkConfigModel = NetworkConfigModel(),
        auth: AuthModel = AuthModel(),
        creation_date: str = None,
        price: dict = {},
        notes: dict = {},
        cloudinit: dict = None,
        region: str = os.environ.get("PROVIDER_REGION", "us-east1"),
        vm_tags: list[str] = None,
    ):
        self.client_uuid = client_uuid
        self.vm_name = vm_name
        self.volumes = volumes if volumes is not None else []
        self.billing_uuid = billing_uuid
        self.vm_uuid = vm_uuid
        self.cpu = cpu
        self.mem = mem
        self.pci = pci
        self.misc = misc
        self.network_config = network_config
        self.private_network_config = private_network_config
        self.auth = auth
        self.creation_date = creation_date
        self.price = price
        self.notes = notes
        self.cloudinit = cloudinit
        self.region = region
        self.vm_tags = vm_tags

    @staticmethod
    def from_json(json_request: dict, client_uuid: str):
        json_request["req"] = json.loads(json_request["req"]) if type(json_request["req"]) is str else json_request["req"]
        volumes = []

        for volume in json_request["volumes"]:
            volumes.append(Storage.from_json(volume))

        cpu = CpuModel.from_json(json_request["req"]["cpu"])
        mem = MemoryModel.from_json(json_request["req"]["mem"])

        pcidevs = []
        if "devices" in json_request["req"]["pci"]:
            for key, value in json_request["req"]["pci"]["devices"].items():
                pcidevs.append(PciDevModel.from_json(key, value))

        misc = MiscModel.from_json(json_request["req"]["misc"])
        auth = AuthModel()
        if "authentication" in json_request.keys():
            auth = AuthModel.from_json(json_request["authentication"])
        elif "authentication" in json_request["req"].keys():
            auth = AuthModel.from_json(json_request["req"]["authentication"])

        return VmModel(
            client_uuid=client_uuid,
            vm_name=json_request["vm_name"],
            volumes=volumes,
            cpu=cpu,
            mem=mem,
            pci=pcidevs,
            misc=misc,
            auth=auth,
            cloudinit=json_request.get("cloudinit", None),
            region=json_request["region"],
        )

    @staticmethod
    def from_json_canallocate(request: dict):
        cpu = CpuModel.from_json(request["req"]["cpu"])
        mem = MemoryModel.from_json(request["req"]["mem"])

        pcidevs = []
        if "devices" in request["req"]["pci"]:
            for key, value in request["req"]["pci"]["devices"].items():
                pcidevs.append(PciDevModel.from_json(key, value))

        misc = MiscModel.from_json(request["req"]["misc"])
        auth = AuthModel()
        if "authentication" in request.keys():
            auth = AuthModel.from_json(request["authentication"])
        elif "authentication" in request["req"].keys():
            auth = AuthModel.from_json(request["req"]["authentication"])
            
        region = request.get("region")
        return VmModel(
            cpu=cpu,
            mem=mem,
            pci=pcidevs,
            misc=misc,
            auth=auth,
            region=region,
            cloudinit=request.get("cloudinit", None),
        )

    @staticmethod
    def from_gcp_json(gcp_data: dict):
        labels = gcp_data.get("labels", {})
        machine_details = gcp_data.get("_machine_type_details", {}) or {}

        cpu = CpuModel(
            slots=machine_details.get("guestCpus", 1),
            fullPhysical=not machine_details.get("isSharedCpu", False),
            arch=[gcp_data.get("cpuPlatform", "X86_64")],
        )

        mem = MemoryModel(capacity=machine_details.get("memoryMb", 1024))

        nics = gcp_data.get("networkInterfaces", [])
        nic = nics[0] if nics else {}
        pub_ipv4 = None
        if "accessConfigs" in nic and nic["accessConfigs"]:
            pub_ipv4 = nic["accessConfigs"][0].get("natIP")

        net_cfg = NetworkConfigModel(ipv4=pub_ipv4, mac=nic.get("macAddress"))
        priv_net_cfg = NetworkConfigModel(ipv4=nic.get("networkIP"), mac=nic.get("macAddress"))

        misc = MiscModel(os_family=labels.get("os_family"), os_flavour=labels.get("os_flavour"))

        volumes = []
        for disk in gcp_data.get("disks", []):
            details = disk.get("_source_disk_details", {}) or {}
            disk_labels = details.get("labels", {}) or {}

            mock_volume_payload = {
                "volumeID": disk_labels.get("billing-uuid") or details.get("id"),
                "creatorID": disk_labels.get("creator-id") or labels.get("client_uuid"),
                "name": details.get("name") or disk.get("deviceName", "unknown-disk"),
                "private": disk_labels.get("private", "false").lower() == "true",
                "readonly": disk_labels.get("readonly", "false").lower() == "true",
                "shareable": disk_labels.get("shareable", "false").lower() == "true",
                "bootable": disk.get("boot", False) or disk_labels.get("bootable", "false").lower() == "true",
                "clonable": disk_labels.get("clonable", "false").lower() == "true",
                "size": int(details.get("sizeGb", 0)) if details.get("sizeGb") else int(disk.get("diskSizeGb", 0)),
                "priority": int(disk_labels.get("priority", 50)) if disk_labels.get("priority") else 50,
                "volume_tags": disk_labels.get("tags", []),
                "type": disk_labels.get("type"),
                "region": gcp_data.get("zone", "").split("/")[-1]
            }

            volumes.append(Storage.from_json(mock_volume_payload))

        return VmModel(
            region=gcp_data.get("zone", "").split("/")[-1],
            client_uuid=labels.get("client_uuid"),
            vm_name=gcp_data.get("name"),
            vm_uuid=gcp_data.get("id"),
            volumes=volumes,
            billing_uuid=labels.get("billing_uuid"),
            cpu=cpu,
            mem=mem,
            misc=misc,
            network_config=net_cfg,
            private_network_config=priv_net_cfg,
            creation_date=gcp_data.get("creationTimestamp"),
        )

    def to_json(self):
        pci_dict = {}
        for pci in self.pci:
            pci_dict.update(pci.to_json())
        return {
            "region": self.region,
            "client_uid": self.client_uuid,
            "vm_name": self.vm_name,
            "volumes": [volume.to_json() for volume in self.volumes] if self.volumes else [],
            "billing_uuid": self.billing_uuid,
            "vm_uid": self.vm_uuid,
            "cpu": self.cpu.to_json() if self.cpu is not None else None,
            "mem": self.mem.to_json() if self.mem is not None else None,
            "pci": {"devices": pci_dict},
            "misc": self.misc.to_json() if self.misc is not None else None,
            "network_config": self.network_config.to_json() if self.network_config is not None else None,
            "private_network_config": self.private_network_config.to_json() if self.private_network_config is not None else None,
            "authentication": self.auth.to_json() if self.auth is not None else None,
            "creation_date": self.creation_date,
            "notes": self.notes,
            "xml": "",
            "vm_tags": self.vm_tags,
        }

    def to_json_register(self):
        pci_dict = {}
        for pci in self.pci:
            pci_dict.update(pci.to_json())
        return {
            "registered": True,
            "uniqueID": self.vm_uuid,
            "req_json": {
                "slots": self.cpu.slots,
                "overprovision": self.cpu.maxOverprovision,
                "allowSMT": self.cpu.fullPhysical,
                "arch": self.cpu.arch,
                "flags": self.cpu.flags,
                "ramsize": self.mem.capacity / 1024,
                "reqECC": self.mem.requireECC,
                "volumes": [volume.to_json_response() for volume in self.volumes] if self.volumes else [],
                "pcidevs": {"devices": pci_dict},
                "netdevs": [],
                "os_family": self.misc.os_family,
                "os_flavour": self.misc.os_flavour,
                "vm_name": self.vm_name,
                "creation_date": self.creation_date,
                "network_config": {
                    "ipv4": self.network_config.ipv4,
                    "mac": self.network_config.mac,
                },
                "autostart": False,
                "firmware": "",
                "networks": [],
                "qemu_agent": "",
            },
            "xml": ""
        }

    def to_json_running(self) -> dict:
        pci_dict = {}
        for pci in self.pci:
            pci_dict.update(pci.to_json())

        env_suffix = "dev." if os.environ.get("ENV") == "development" else ""

        return {
            "uniqueID": self.vm_uuid,
            "req_json": {
                "slots": self.cpu.slots,
                "overprovision": self.cpu.maxOverprovision,
                "allowSMT": self.cpu.fullPhysical,
                "arch": self.cpu.arch,
                "flags": self.cpu.flags,
                "ramsize": self.mem.capacity / 1024,
                "reqECC": self.mem.requireECC,
                "volumes": [volume.to_json_response() for volume in self.volumes] if self.volumes else [],
                "pcidevs": [],
                "netdevs": [],
                "os_family": self.misc.os_family,
                "os_flavour": self.misc.os_flavour,
                "vm_name": self.vm_name,
                "creation_date": self.creation_date,
                "network_config": {
                    "dom_display": {"port": 5900, "protocol": "vnc"},
                    "interface": "vnet102",
                    "is_reachable_from_host": False,
                    "model": "virtio",
                    "name": "",
                    "source": "default",
                    "type": "network",
                    "ipv4": self.network_config.ipv4,
                    "ipv6": self.network_config.ipv6,
                    "mac": self.network_config.mac,
                },
                "networks": [],
                "private_network_config": [
                    {
                        "ipv4": self.private_network_config.ipv4,
                        "ipv6": self.private_network_config.ipv6,
                        "mac": self.private_network_config.mac,
                    },
                ],
            },
            "xml": "",
            "target_type": "meson",
            "serverurl": f"https://{os.environ.get('PROVIDER', 'gcp')}.{env_suffix}meson.elemento.cloud:7777",
            "states": "running",
            "vm_tags": self.vm_tags,
            "billing_uuid": self.billing_uuid,
            "region": self.region,
            "service_uuid": self.vm_uuid
        }
        
    def to_elemento_dict(self):
        return self.to_json_running()