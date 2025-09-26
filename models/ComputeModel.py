import os
from models.StorageModel import ElementoStorage

class ElementoCpu:
    """
    Describes the cpu configuration of the machine.

    Attributes:
        slots (int): The number of cores that the cpu has.
        fullPhysical (bool): If the cpu is full physical.
        maxOverprovision (int): The maximum number of vm per core.
        min_frequency (float): The minimum frequency of the cpu.
        arch (list[str]): The architectures for the cpu.
        flags (list[str]): The instruction sets that the cpu will use.
    """

    def __init__(
        self,
        slots: int = 1,
        fullPhysical: bool = False,
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

    def to_json(self):
        return {
            "slots": self.slots,
            "fullPhysical": self.fullPhysical,
            "maxOverprovision": self.maxOverprovision,
            "min_frequency": self.min_frequency,
            "arch": [arch for arch in self.arch],
            "flags": [flag for flag in self.flags],
        }


class ElementoMemory:
    """
    Describes the memory configuration of the machine.

    Attributes:
        capacity (int): The capacity of the memory in MB.
        requireECC (bool): If the memory requires the error correcting code.
    """

    def __init__(
        self,
        capacity: int = 1024,
        requireECC: bool = False,
    ):
        self.capacity = int(capacity)
        self.requireECC = requireECC

    def to_json(self):
        return {"capacity": self.capacity, "requireECC": self.requireECC}


class ElementoPciDev:
    """
    Describes the PCI devices configuration of the machine.

    All the PCI devices
    supported by Elemento are visible at [https://github.com/Elemento-Modular-Cloud/elemento-pciid-mapper]
    Attributes:
        vendor (str): The vendor of the PCI device.
        model (str): The model of the PCI device.
        quantity (int): The quantity of the PCI device.
    """

    def __init__(
        self,
        vendor: str = None,
        model: str = None,
        quantity: int = 0,
    ):
        self.vendor = vendor
        self.model = model
        self.quantity = int(quantity)

    def to_json(self):
        return {f"{self.vendor}:{self.model}": self.quantity}


class ElementoMisc:
    """
    Describes the OS configuration of the machine.

    All the Images
    supported by Elemento are visible at [https://github.com/Elemento-Modular-Cloud/iso-templates/blob/main/iso.json]
    Attributes:
        os_family (str): The OS family of the machine.
        It can be Windows or Linux.
        os_flavour (str): The OS flavour of the machine.
    """

    def __init__(
        self,
        os_family: str = None,
        os_flavour: str = None,
    ):
        self.os_family = os_family
        self.os_flavour = os_flavour

    def to_json(self):
        return {"os_family": self.os_family, "os_flavour": self.os_flavour}


class ElementoNetworkConfig:
    """
    Describes the network configuration of the machine.

    Every machine has his own public IP.

    Attributes:
        ipv4 (str): The public IP of the machine.
        mac (str): The MAC address of the machine.
    """

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


class ElementoAuth:
    """
    Describes the authentication configuration required for the machine.

    For some operating systems, the ssh key can't be used (e.g. Windows), so it's important to check
    and use all the authentication ways properly.

    Attributes:
        ssh_key (str): The ssh key that will be used to access the machine.
        username (str): The username that will be used to access the machine.
        password (str): The password that will be used to access the machine.
    """

    def __init__(
        self,
        ssh_key: str = None,
        username: str = None,
        password: str = None,
    ):
        self.ssh_key = ssh_key
        self.username = username
        self.password = password

    def to_json(self):
        return {
            "ssh_key": self.ssh_key,
            "username": self.username,
            "password": self.password,
        }


class ElementoMachine:
    """
    Describes a machine configuration to be created.

    Use this class and its underlying classes to create and manage a machine on the csp.
    Some ids (client_uuid, vm_uuid, billing_uuid) MUST be setted inside the machine on the csp to retrieve them.
    These ids are fundamental for the Meson to work properly.

    Attributes:
        csp_region (str): The region where the machine will be created. --> maybe will be removed
        client_uuid (str): The client's unique identifier from Elemento.
        vm_name (str): The name of the machine that will be displayed in the response.
        volumes (list[ElementoStorage]): The volume models that will be attached to the machine.
        if the id is given, the volume already exists otherwise it has to be created from the given configuration.
        billing_uuid (str): The billing id that will be used to charge the client.
        vm_uuid (str): The unique identifier of the machine.
        cpu (ElementoCpu): The cpu configuration of the machine.
        mem (ElementoMemory): The memory configuration of the machine.
        pci (list[ElementoPciDev]): The pci devices configuration of the machine.
        misc (ElementoMisc): The OS configuration of the machine.
        network_config (ElementoNetworkConfig): The network configuration of the machine.
        auth (ElementoAuth): The authentication configuration required for the machine.
        creation_date (str): The creation date of the machine.
        It MUST be updated when the machine is created (%m/%d/%Y, %H:%M:%S).
        notes (dict): A dictionary with a totally free space to add info about the machine.
        It can be used to store any kind of information useful for the Meson implementation.
        All the information won't be displayed in the Elemento's response.
    """

    def __init__(
        self,
        csp_region: str = None,
        client_uuid: str = None,
        vm_name: str = None,
        volumes: list[ElementoStorage] = None,
        billing_uuid: str = None,
        vm_uuid: str = None,
        cpu: ElementoCpu = None,
        mem: ElementoMemory = None,
        pci: list[ElementoPciDev] = None,
        misc: ElementoMisc = None,
        network_config: ElementoNetworkConfig = None,
        private_network_config: ElementoNetworkConfig = None,
        auth: ElementoAuth = None,
        creation_date: str = None,
        notes: dict = dict(),
    ):
        self.csp_region = csp_region
        self.client_uuid = client_uuid
        self.vm_name = vm_name
        self.volumes = volumes
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
        self.notes = notes

    def to_json(self):
        """
        create a dict from an ElementoMachine object with all fields

        Returns:
            A json version of the ElementoMachine.
        """
        pci_dict = {}
        for pci in self.pci:
            pci_dict.update(pci.to_json())
        return {
            "csp_region": self.csp_region,
            "client_uuid": self.client_uuid,
            "vm_name": self.vm_name,
            "volumes": (
                [volume.to_json() for volume in self.volumes]
                if self.volumes is not None
                else list()
            ),
            "billing_uuid": self.billing_uuid,
            "vm_uuid": self.vm_uuid,
            "cpu": self.cpu.to_json() if self.cpu is not None else None,
            "mem": self.mem.to_json() if self.mem is not None else None,
            "pci": {
                "devices": pci_dict if self.pci is not None else dict()
            },
            "misc": self.misc.to_json() if self.misc is not None else None,
            "network_config": (
                self.network_config.to_json()
                if self.network_config is not None
                else None
            ),
            "private_network_config": (
                self.private_network_config.to_json()
                if self.private_network_config is not None
                else None
            ),
            "authentication": self.auth.to_json() if self.auth is not None else None,
            "creation_date": self.creation_date,
            "notes": self.notes,
        }

    def to_json_register(self):
        """
        create a dict from an ElementoMachine object for the register response

        Returns:
            A dict for the register response.
        """
        pci_dict = {}
        for pci in self.pci:
            pci_dict.update(pci.to_json())
        return {
            "uniqueID": self.vm_uuid,
            "req_json": {
                "slots": self.cpu.slots,
                "overprovision": self.cpu.maxOverprovision,
                "allowSMT": self.cpu.fullPhysical,
                "arch": self.cpu.arch,
                "flags": self.cpu.flags,
                "ramsize": self.mem.capacity,
                "reqECC": self.mem.requireECC,
                "volumes": (
                    [volume.to_json() for volume in self.volumes]
                    if self.volumes is not None
                    else list()
                ),
                "pcidevs": {
                    "devices": pci_dict if self.pci is not None else dict()
                },
                "netdevs": [],
                "os_family": self.misc.os_family,
                "os_flavour": self.misc.os_flavour,
                "vm_name": self.vm_name,
                "creation_date": self.creation_date,
                "network_config": {
                    "ipv4": self.network_config.ipv4,
                    "mac": self.network_config.mac,
                },
            },
            "xml": "",
        }

    def to_json_status(self) -> dict:
        """A toJson method for the statusjson API response.

        Returns:
            The dict for the statusjson api response
        """
        pci_dict = {}
        for pci in self.pci:
            pci_dict.update(pci.to_json())
        return {
            "cpu": {
                "SMTOn": True,
                "SMTRatio": 0,
                "arch": self.cpu.arch,
                "flags": self.cpu.flags,
                "frequency": self.cpu.min_frequency,
                "max_cores": self.cpu.slots,
                "max_threads": self.cpu.maxOverprovision,
                "ncores": self.cpu.slots,
                "used_cores": 0,
                "used_threads": 0,
                "vendorID": "",
            },
            "manufacturer": "",
            "mem": {
                "avail": self.mem.capacity,
                "isECC": self.mem.requireECC,
                "size": self.mem.capacity,
            },
            "pci": {
                "devices": pci_dict if self.pci is not None else dict()
            },
        }

    def to_json_running(self, price: dict) -> dict:
        """A toJson method for the running API response.

        Returns:
            The dict for the running api response
        """
        pci_dict = {}
        for pci in self.pci:
            pci_dict.update(pci.to_json())
        return {
            "uniqueID": self.vm_uuid,
            "req_json": {
                "slots": self.cpu.slots,
                "overprovision": self.cpu.maxOverprovision,
                "allowSMT": self.cpu.fullPhysical,
                "arch": self.cpu.arch,
                "flags": self.cpu.flags,
                "ramsize": self.mem.capacity,
                "reqECC": self.mem.requireECC,
                "volumes": (
                    [volume.to_json() for volume in self.volumes]
                    if self.volumes is not None
                    else list()
                ),
                "pcidevs": {
                    "devices": pci_dict if self.pci is not None else dict()
                },
                "netdevs": [],
                "os_family": self.misc.os_family,
                "os_flavour": self.misc.os_flavour,
                "vm_name": self.vm_name,
                "creation_date": self.creation_date,
                "network_config": {
                    "ipv4": self.network_config.ipv4,
                    "ipv6": self.network_config.ipv6,
                    "mac": self.network_config.mac,
                },
                "private_network_config": [
                    {
                        "ipv4": self.private_network_config.ipv4,
                        "ipv6": self.private_network_config.ipv6,
                        "mac": self.private_network_config.mac,
                    },
                ],
            },
            "mesos": {"provider": os.getenv("PROVIDER"), "price": price},
            "xml": "<domain></domain>",
        }

    def to_json_canallocate(self, price: dict) -> dict:
        """A toJson method for the canallocate API response.

        Args:
            price (dict): Pricing dict details

        Returns:
            The dict for the canallocate api response
        """
        return {"canallocate": True, "price": price}


class ElementoMetrics:
    """
    Describes the metrics of the machine.

    Attributes:
        itemID (str): The unique identifier of the machine.
        status (str): The status of the machine.
        creationDate (str): The creation date of the machine.
        lastUpdateDate (str): The last update date of the machine.
    """

    def __init__(
        self,
        itemID: str = None,
        status: str = None,
        creationDate: str = None,
        lastUpdateDate: str = None,
    ):
        self.itemID = itemID
        self.status = status
        self.creationDate = creationDate
        self.lastUpdateDate = lastUpdateDate

    def to_json(self):
        return {
            "itemID": self.itemID,
            "status": self.status,
            "creationDate": self.creationDate,
            "lastUpdateDate": self.lastUpdateDate,
        }
