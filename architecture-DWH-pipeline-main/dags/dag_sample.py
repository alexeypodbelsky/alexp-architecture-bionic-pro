from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime
import csv
import os

# Аргументы по умолчанию: владелец процесса и время отсчета для задачи
default_args = {
    "owner": "airflow",
    "start_date": datetime(2024, 12, 1),
}


# Функция для чтения данных из CSV-файлов, их объединения и генерации SQL запросов
def generate_combined_insert_queries():
    CRM_FILE_PATH = "sample_files/crm_data.csv"
    SENSORS_FILE_PATH = "sample_files/sensors_data.csv"
    OUTPUT_SQL_FILE_PATH = "./dags/sql/insert_queries.sql"

    # 1. Читаем crm_data.csv и сохраняем в словаре для быстрого доступа
    crm_data = {}
    try:
        with open(CRM_FILE_PATH, "r", encoding="utf-8") as crmfile:
            csvreader = csv.reader(crmfile)
            header = next(csvreader)  # Пропускаем заголовок
            # user_name,email,firstName,lastName
            user_name_idx = header.index("user_name")
            email_idx = header.index("email")
            first_name_idx = header.index("firstName")
            last_name_idx = header.index("lastName")

            for row in csvreader:
                if row:  # Убедимся, что строка не пустая
                    user_name = row[user_name_idx]
                    crm_data[user_name] = {
                        "email": row[email_idx],
                        "firstName": row[first_name_idx],
                        "lastName": row[last_name_idx],
                    }
    except FileNotFoundError:
        raise FileNotFoundError(f"CRM file not found at {CRM_FILE_PATH}")
    except Exception as e:
        raise Exception(f"Error reading CRM data: {e}")

    # 2. Читаем sensors_data.csv, объединяем с crm_data и генерируем SQL запросы
    insert_queries = []
    try:
        with open(SENSORS_FILE_PATH, "r", encoding="utf-8") as sensorsfile:
            csvreader = csv.reader(sensorsfile)
            header = next(csvreader)  # Пропускаем заголовок
            # record_id,utc_date_time,user_name,sensor_name,value
            record_id_idx = header.index("record_id")
            utc_date_time_idx = header.index("utc_date_time")
            user_name_idx_s = header.index("user_name")  # user_name из sensors_data
            sensor_name_idx = header.index("sensor_name")
            value_idx = header.index("value")

            for row in csvreader:
                if not row:  # Пропускаем пустые строки
                    continue

                # Данные из sensors_data
                record_id = row[record_id_idx]
                utc_date_time_str = row[utc_date_time_idx]
                user_name_sensor = row[user_name_idx_s]
                sensor_name = row[sensor_name_idx]
                value = row[value_idx]

                # Форматируем дату/время для PostgreSQL (YYYY-MM-DD HH:MM:SS)
                # Исходный формат: 'DD.MM.YYYY-HH:MM:SS'
                try:
                    dt_object = datetime.strptime(
                        utc_date_time_str, "%d.%m.%Y-%H:%M:%S"
                    )
                    formatted_dt = dt_object.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError as ve:
                    print(
                        f"Warning: Could not parse date '{utc_date_time_str}'. Skipping or using raw string. Error: {ve}"
                    )
                    formatted_dt = (
                        utc_date_time_str  # В случае ошибки используем сырую строку
                    )

                # Ищем данные пользователя из crm_data
                crm_info = crm_data.get(
                    user_name_sensor,
                    {
                        "email": "N/A",  # Указываем 'N/A' или None, если пользователь не найден в CRM
                        "firstName": "N/A",
                        "lastName": "N/A",
                    },
                )

                # Генерируем запрос
                insert_query = f"""
                INSERT INTO sample_table (record_id, utc_date_time, user_name, email, firstName, lastName, sensor_name, value)
                VALUES (
                    {record_id},
                    '{formatted_dt}',
                    '{user_name_sensor}',
                    '{crm_info['email']}',
                    '{crm_info['firstName']}',
                    '{crm_info['lastName']}',
                    '{sensor_name}',
                    {value}
                );
                """
                insert_queries.append(insert_query)
    except FileNotFoundError:
        raise FileNotFoundError(f"Sensors file not found at {SENSORS_FILE_PATH}")
    except Exception as e:
        raise Exception(f"Error reading Sensors data or generating queries: {e}")

    # 3. Сохраняем сгенерированные запросы в SQL-файл
    with open(OUTPUT_SQL_FILE_PATH, "w", encoding="utf-8") as f:
        for query in insert_queries:
            f.write(f"{query}\n")


# Определяем DAG
with DAG(
    "crm_sensors_to_postgres_dag",
    default_args=default_args,
    schedule_interval="@once",
    catchup=False,
    tags=["data_ingestion", "etl"],
) as dag:

    # Создаем таблицу в PostgreSQL
    create_crm_sensor_table = PostgresOperator(
        task_id="create_crm_sensor_table",
        postgres_conn_id="write_to_postgres",
        sql="""
        DROP TABLE IF EXISTS sample_table;
        CREATE TABLE sample_table (
            record_id BIGINT PRIMARY KEY,
            utc_date_time TIMESTAMP,
            user_name VARCHAR(255),
            email VARCHAR(255),
            firstName VARCHAR(255),
            lastName VARCHAR(255),
            sensor_name VARCHAR(255),
            value NUMERIC(18,2)
        );
        """,
    )

    # Оператор для генерации SQL-запросов
    generate_combined_queries = PythonOperator(
        task_id="generate_combined_insert_queries",
        python_callable=generate_combined_insert_queries,
    )

    # Запускаем выполнение оператора PostgresOperator для вставки данных
    run_combined_insert_queries = PostgresOperator(
        task_id="run_combined_insert_queries",
        postgres_conn_id="write_to_postgres",
        sql="sql/insert_queries.sql",
    )

    # Определяем порядок выполнения задач
    create_crm_sensor_table >> generate_combined_queries >> run_combined_insert_queries
