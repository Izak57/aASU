from requests import Session
from rich import print



s = Session()

base_url = "http://localhost:8080"

s.post(base_url + "/users/izak/new", json={
    "name": "Izak",
    "email": "izak@tuffapi.com",
    "birth": "2009-08-03"
})


r = s.get(base_url + "/users/izak")
print(r.json())
