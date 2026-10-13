from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="FTGO Supplier Service — Business Capability Example",
    description="One service boundary aligned with the Supplier Management capability.",
    version="1.0.0",
)

restaurants: dict[int, dict] = {}
couriers: dict[int, dict] = {}


class RestaurantCreate(BaseModel):
    name: str


class MenuUpdate(BaseModel):
    items: list[str]


class CourierCreate(BaseModel):
    name: str


class AvailabilityUpdate(BaseModel):
    available: bool


@app.get("/architecture")
def architecture():
    return {
        "strategy": "decompose by business capability",
        "capability": "Supplier Management",
        "service": "Supplier Service",
        "responsibilities": ["restaurant management", "courier management"],
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


@app.post("/couriers")
def create_courier(payload: CourierCreate):
    courier_id = len(couriers) + 1
    courier = {"id": courier_id, "name": payload.name, "available": False}
    couriers[courier_id] = courier
    return courier


@app.patch("/couriers/{courier_id}/availability")
def update_availability(courier_id: int, payload: AvailabilityUpdate):
    courier = couriers.get(courier_id)
    if courier is None:
        raise HTTPException(status_code=404, detail="Courier not found")
    courier["available"] = payload.available
    return courier


@app.get("/suppliers")
def list_suppliers():
    return {"restaurants": list(restaurants.values()), "couriers": list(couriers.values())}
