API_SECRET = 'shhh'

PASSWORD = 'password'

DB = {
    "host": "localhost",
    "port": 27017,
    "name": "metrics",
    "username": "metrics",
    "password": "password"
}

FUNNELS = [
    {
        "name": "homepage->done",
        "steps": ["/", "/done"]
    },
    {
        "name": "main workflow",
        "steps": ["/", "/authenticate", "/settings", "/done"]
    }
]
