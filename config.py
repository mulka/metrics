db = {
	"host": "localhost",
	"port": 27017,
	"name": "metrics",
	"username": "metrics",
	"password": "password"
}

funnels = [
    {
        "name": "homepage->done",
        "steps": ["/", "/done"]
    },
    {
        "name": "main workflow",
        "steps": ["/", "/authenticate", "/settings", "/done"]
    }
]
