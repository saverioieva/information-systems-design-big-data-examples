from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="FTGO Restaurant Service — DDD Example",
    description="Restaurant bounded context with its own model and vocabulary.",
    version="1.0.0",
)

restaurants: dict[int, dict] = {}


class RestaurantCreate(BaseModel):
    name: str


class MenuUpdate(BaseModel):
    items: list[str]


@app.get("/architecture")
def architecture():
    return {
        "strategy": "decompose by subdomain / bounded context",
        "subdomain": "Restaurant",
        "service": "Restaurant Service",
        "domain_concepts": ["Restaurant", "Menu", "MenuItem"],
    }


@app.post("/restaurants")
def create_restaurant(payload: RestaurantCreate):
    restaurant_id = len(restaurants) + 1
    restaurant = {"id": restaurant_id, "name": payload.name, "menu": []}
    restaurants[restaurant_id] = restaurant
    return restaurant


@app.patch("/restaurants/{restaurant_id}/menu")
def update_menu(restaurant_id: int, payload: MenuUpdate):
    restaurant = restaurants.get(restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    restaurant["menu"] = payload.items
    return restaurant


@app.get("/restaurants/{restaurant_id}")
def get_restaurant(restaurant_id: int):
    restaurant = restaurants.get(restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant
