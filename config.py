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

TESTS = [
    {
        "id":"finalPage",
        "variations":[
            {"id":"done"},
            {"id":"subscribe", "weight": 0}
        ]
    },
    {
        "id": "firstButtonText",
        "variations":[
            {"id":"go"},
            {"id":"start"}
        ]
    }
]