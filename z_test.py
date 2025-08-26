import requests

API_KEY = "7e9cb50eef4349ad85d99c10559e00188fe83306042c9693d56df6e2f6cbb053"
url = "https://serpapi.com/search.json"

params = {
    "q": "Coffee",
    "api_key": API_KEY
}

response = requests.get(url, params=params)

print("Status Code:", response.status_code)
print(response.json())
