import os

import swagger_client


BASE_URL = os.getenv("ORDER_API_BASE_URL", "http://order-fastapi:8000")


def main() -> None:
    configuration = swagger_client.Configuration()
    configuration.host = BASE_URL

    api = swagger_client.DefaultApi(swagger_client.ApiClient(configuration))
    request = swagger_client.CreateOrderRequest(restaurant_id=42, total=25.50)

    created = api.create_order(request)
    print("Created with Swagger-generated client:", created)

    fetched = api.get_order(created.id)
    print("Fetched with Swagger-generated client:", fetched)


if __name__ == "__main__":
    main()
