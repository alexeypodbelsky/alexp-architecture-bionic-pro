import os
from flask import Flask, jsonify, request, abort
from jose import jwt
from jose.exceptions import JWTError
import requests
from functools import wraps
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

# --- Конфигурация Keycloak ---
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM")
KEYCLOAK_AUDIENCE = os.environ.get("KEYCLOAK_CLIENT_ID")

if not all([KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_AUDIENCE]):
    print(
        "Error: Missing Keycloak environment variables. Please check your .env file or environment setup."
    )
    print(f"KEYCLOAK_URL: {KEYCLOAK_URL}")
    print(f"KEYCLOAK_REALM: {KEYCLOAK_REALM}")
    print(f"KEYCLOAK_AUDIENCE: {KEYCLOAK_AUDIENCE}")
    exit(1)

KEYCLOAK_CERTS_URL = (
    f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
)

_keycloak_public_keys = None


def get_keycloak_public_keys():
    global _keycloak_public_keys
    if _keycloak_public_keys is None:
        print(f"Fetching public keys from: {KEYCLOAK_CERTS_URL}")
        try:
            response = requests.get(KEYCLOAK_CERTS_URL)
            response.raise_for_status()
            _keycloak_public_keys = response.json()
            print("Public keys fetched successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Keycloak public keys: {e}")
            abort(500, description="Could not fetch Keycloak public keys.")
    return _keycloak_public_keys


# --- Декоратор для защиты эндпоинтов ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Если это OPTIONS-запрос (preflight), просто пропускаем его,
        # Flask-CORS уже позаботился о заголовках.
        if request.method == "OPTIONS":
            return "", 200

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            abort(401, description="Authorization header missing.")

        try:
            token_type, token = auth_header.split(None, 1)
        except ValueError:
            abort(401, description="Invalid Authorization header format.")

        if token_type.lower() != "bearer":
            abort(
                401,
                description="Unsupported authorization type. Only Bearer is allowed.",
            )

        try:
            public_keys = get_keycloak_public_keys()

            claims = jwt.decode(
                token,
                public_keys,
                algorithms=["RS256"],
                audience=KEYCLOAK_AUDIENCE,
                issuer=f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}",
            )

            request.user_id = claims.get("sub")
            request.username = claims.get("preferred_username")

        except JWTError as e:
            print(f"Token validation failed: {e}")
            abort(401, description=f"Invalid token: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during token validation: {e}")
            abort(500, description="Internal server error during token validation.")

        return f(*args, **kwargs)

    return decorated


# --- Эндпоинт для получения отчетов ---
@app.route("/reports", methods=["GET", "OPTIONS"])
@token_required
def get_report():
    user_id = request.user_id
    username = request.username

    report_data = {
        "userId": user_id,
        "username": username,
        "reportType": "ProsthesisUsage",
        "period": "Last Month",
        "summary": "This is a hardcoded report for your prosthesis usage.",
        "details": {
            "totalMovements": 12345,
            "averageReactionTimeMs": 95,
            "batteryCycles": 30,
            "lastCalibrationDate": "2023-10-26",
            "prosthesisModel": "BionicPRO X-200",
        },
        "disclaimer": "This report is for informational purposes only.",
    }

    user_email = "prothetic@example.com"
    user_first_name = "Adam"
    user_last_name = "Jensen"
    report_date = "24.11.2025-21:12:02"

    gen_report = {
        "user_name": username,
        "email": user_email,
        "firstName": user_first_name,
        "lastName": user_last_name,
        "reportDate": report_date,
        "sensor_data": {
            "utc_date_time": "24.11.2025-20:47:01",
            "sensor_name": "totalMovements",
            "value": 12345,
        },
        "sensor_data": {
            "utc_date_time": "24.11.2025-20:47:02",
            "sensor_name": "average5MinReactionTimeMs",
            "value": 95,  # не может быть более 110
        },
        "sensor_data": {
            "utc_date_time": "24.11.2025-20:47:03",
            "sensor_name": "battery_percent",
            "value": 50,  # не может быть более 100
        },
        "sensor_data": {
            "utc_date_time": "24.11.2025-20:50:05",
            "sensor_name": "battery_percent",
            "value": 49,  # не может быть более 100
        },
    }

    return jsonify(report_data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
