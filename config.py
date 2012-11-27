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
    },
    {
        "id": "collectEmail",
        "variations":[
            {"id": "true"},
            {"id": "false"}
        ]
    }
]