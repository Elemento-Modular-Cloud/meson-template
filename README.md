# Meson Template
A template repository for creating provider meson implementations.

## Structure
- `main_service.py`: The main entry point for the meson, containing the FastAPI application and route definitions for services.
- `main_compute.py`: The main entry point for the meson, containing the FastAPI application and route definitions for compute operations.
- `main_storage.py`: The main entry point for the meson, containing the FastAPI application and route definitions for storage operations.
- `infrastructure`: Contains the compute and storage related function implementations.
- `platforms`: Contains the PaaS related services function implementations.
- `software`: Contains the SaaS related services function implementations.
- `commons/provider_iam`: Contains the authentication functions on external cloud provider.
- `commons/utils`: Contains utility functions that can be used/useful across the meson.
- `commons/elemento_iam`: Contains the Elemento IAM related functions, MUST not be touched.

All the logs must use the Logging functionality, here are the possible log levels:
```python
import logging
logging.debug("This is a debug log")
logging.info("This is an info log")
logging.warning("This is a warning log")
logging.error("This is an error log")
logging.critical("This is a critical log")
```

### Usage
1. Download submodules:
```bash
git submodule update --init --recursive
```
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Generate dummy TLS certificates for testing:
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key \
  -out tls.crt \
  -subj "/CN=localhost"
```
4. Run the mesons:
```bash
docker compose up --build
```