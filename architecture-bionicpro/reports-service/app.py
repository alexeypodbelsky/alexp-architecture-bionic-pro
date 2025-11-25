import os
from flask import Flask, jsonify, request, abort
from jose import jwt
from jose.exceptions import JWTError
import requests
from functools import wraps
from dotenv import load_dotenv
from flask_cors import CORS
import psycopg2
from datetime import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

# --- Конфигурация Keycloak ---
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM")
KEYCLOAK_AUDIENCE = os.environ.get("KEYCLOAK_CLIENT_ID")

# --- Конфигурация базы данных ---
DB_HOST = "localhost"
DB_NAME = "sample"
DB_USER = "airflow"
DB_PASS = "airflow"
DB_PORT = "5432"

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
    username = request.username

    if not username:
        return (
            jsonify({"message": "Username not provided by token_required decorator"}),
            401,
        )

    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT
        )
        cur = conn.cursor()

        sql_query = """
            SELECT utc_date_time, user_name, email, firstName, lastName, sensor_name, value
            FROM sample_table
            WHERE user_name = %s
            ORDER BY utc_date_time;
        """
        cur.execute(sql_query, (username,))
        rows = cur.fetchall()

        if not rows:
            return jsonify({"message": f"No data found for user: {username}"}), 404

        first_row = rows[0]
        user_email = first_row[2]
        user_first_name = first_row[3]
        user_last_name = first_row[4]

        sensor_data_list = []
        for row in rows:
            sensor_data_list.append(
                {
                    "utc_date_time": row[0].strftime("%d-%m-%Y %H:%M:%S"),
                    "sensor_name": row[5],
                    "value": row[6],
                }
            )

        report_date_str = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        gen_report = {
            "user_name": username,
            "email": user_email,
            "firstName": user_first_name,
            "lastName": user_last_name,
            "reportDate": report_date_str,
            "sensor_data": sensor_data_list,
        }

        return jsonify(gen_report)

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return (
            jsonify({"error": f"Failed to retrieve data from the database: {e}"}),
            500,
        )
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": f"An internal server error occurred: {e}"}), 500
    finally:
        if conn:
            cur.close()
            conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
