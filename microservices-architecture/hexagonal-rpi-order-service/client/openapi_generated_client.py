import os

import openapi_client
from openapi_client.api.default_api import DefaultApi
from openapi_client.models.create_order_request import CreateOrderRequest


BASE_URL = os.getenv("ORDER_API_BASE_URL", "http://order-fastapi:8000")


def main() -> None:
    configuration = openapi_client.Configuration(host=BASE_URL)

    with openapi_client.ApiClient(configuration) as api_client:
        api = DefaultApi(api_client)
        request = CreateOrderRequest(restaurant_id=42, total=25.50)

        created = api.create_order(create_order_request=request)
        print("Created with OpenAPI-generated client:", created)

        fetched = api.get_order(order_id=created.id)
        print("Fetched with OpenAPI-generated client:", fetched)


if __name__ == "__main__":
    main()
