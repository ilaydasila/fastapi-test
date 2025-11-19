from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from pymongo import MongoClient
from bson import ObjectId
from pymongo.errors import ServerSelectionTimeoutError


app = FastAPI()

# ------- MODELS -------
# What the client sends when creating a coffee (no id)
class CoffeeCreate(BaseModel): # pydantic understands basemodel not python and fastapi can work with it
    name: str
    price: int
    acidic: bool
    description: Optional[str] = None

# What we store and return (has id)
class Coffee(CoffeeCreate):
    id: str


# ------- DATABASES --------
MONGODB_URI = "mongodb://localhost:27017"

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    print("Testing Mongo connection...")
    client.server_info()
    print("Mongo connection OK")
except ServerSelectionTimeoutError as e:
    print("Mongo connection error:", e)
    raise

db = client["coffee_db"]
coffees_collection = db["coffees"]

# ------- ROOT -------
@app.get("/")
def home():
    return {"message": "Coffee Store API is running!"}


# ------- ADD & LIST COFFEES -------
@app.post("/coffees", response_model=Coffee) # Response model belongs to fastapi
def add_coffee(coffee: CoffeeCreate):
    coffee_dict = coffee.dict()
    result = coffees_collection.insert_one(coffee_dict)
    new_doc = coffees_collection.find_one({"_id": result.inserted_id})

    return Coffee(
        id=str(new_doc["_id"]),
        name=new_doc["name"],
        price=new_doc["price"],
        acidic=new_doc["acidic"],
        description=new_doc.get("description"),
    )

@app.post("/coffees/bulk", response_model=List[Coffee])
def add_coffees_bulk(coffees: List[CoffeeCreate]):
    # turn Pydantic models into plain dicts
    docs_to_insert = [coffee.dict() for coffee in coffees]

    # insert many into MongoDB
    result = coffees_collection.insert_many(docs_to_insert)

    # fetch the inserted documents
    inserted_ids = result.inserted_ids
    cursor = coffees_collection.find({"_id": {"$in": inserted_ids}})

    created: List[Coffee] = []
    for doc in cursor:
        created.append(
            Coffee(
                id=str(doc["_id"]),
                name=doc["name"],
                price=doc["price"],
                acidic=doc["acidic"],
                description=doc.get("description"),
            )
        )

    return created

@app.get("/coffees", response_model=List[Coffee])
def list_coffees():
    coffees: List[Coffee] = []
    for doc in coffees_collection.find():
        coffees.append(
            Coffee(
                id=str(doc["_id"]),
                name=doc["name"],
                price=doc["price"],
                acidic=doc["acidic"],
                description=doc.get("description"),
            )
        )
    return coffees

@app.get("/coffees/{coffee_id}", response_model=Coffee)
def get_coffee(coffee_id: str):
    # convert string to ObjectId; if invalid, return 400
    try:
        oid = ObjectId(coffee_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid coffee id")

    doc = coffees_collection.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Coffee not found")

    return Coffee(
        id=str(doc["_id"]),
        name=doc["name"],
        price=doc["price"],
        acidic=doc["acidic"],
        description=doc.get("description")
    )

@app.put("/coffees/{coffee_id}", response_model=Coffee)
def update_coffee(coffee_id: str, coffee_update: CoffeeCreate):
    try:
        oid = ObjectId(coffee_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid coffee id")

    update_result = coffees_collection.update_one(
        {"_id": oid},
        {"$set": coffee_update.dict()},
    )

    if update_result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Coffee not found")

    # fetch updated document
    doc = coffees_collection.find_one({"_id": oid})
    return Coffee(
        id=str(doc["_id"]),
        name=doc["name"],
        price=doc["price"],
        acidic=doc["acidic"],
        description=doc.get("description"),
    )

@app.delete("/coffees/{coffee_id}")
def delete_coffee(coffee_id: str):
    try:
        oid = ObjectId(coffee_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid coffee id")

    delete_result = coffees_collection.delete_one({"_id": oid})

    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Coffee not found")

    return {"message": "Coffee deleted"}