import json

from pymongo import Connection
from bson import Code

from config import DB, FUNNELS, TESTS

db = Connection(
    "mongodb://" + DB["username"] + ":" + DB["password"]
    + "@" + DB["host"] + ":" + str(DB["port"]) + "/" + DB["name"]
)[DB["name"]]

funnels_code = "var funnels = " + json.dumps(FUNNELS) + ";";
tests_code = "var tests = " + json.dumps(TESTS) + ";";

def map_code(code):
    return "function () {" + funnels_code + tests_code + code + "}"

def reduce_code(code):
    return "function (key, values) {" + funnels_code + tests_code + code + "}"

map1 = map_code("""
    var combined_steps = {};

    funnels.forEach(function(funnel){
        funnel.steps.forEach(function(step){
            combined_steps[step] = true;
        });
    });

    for(step in combined_steps){
        if (this.url == step){
            emit(this.session_id, {"events": [{"url": this.url, "timestamp": this.timestamp}]});
            return;
        }
    }
""")

reduce1 = reduce_code("""
    var output = new Array();
    values.forEach(function (value){
        value.events.forEach(function (event){
            output.push(event);
        });
    });
    return {"events": output};
""")

map2 = map_code("""
    emit(this._id, {"events": [], "tests": this.tests})
""")

reduce2 = reduce_code("""
    var output = {};
    output.events = new Array();

    values.forEach(function(value) {
        if("events" in value){
            value.events.forEach(function (event){
                output.events.push(event);
            });
        }
        if("tests" in value){
            output.tests = value.tests
        }
    });

    return output;
""")

map3 = map_code("""
    funnels.forEach(function(funnel){
        var steps = funnel.steps;

        var step_counts = {};
        steps.forEach(function(step){
            step_counts[step] = 0;
        });

        var events = this.value.events;

        events.sort(function(a,b){ return a.timestamp-b.timestamp;});

        var item_data = {};
        steps.forEach(function(step){
            item_data[step] = false;
        });

        events.forEach(function(event){
            var url = event.url;
            for(i in steps){
                var step = steps[i];
                if((i == 0 || item_data[steps[i-1]]) && url == step){
                    item_data[step] = true;
                }
            }
        });

        steps.forEach(function(step){
            if(item_data[step]){
                step_counts[step]++;
            }
        });

        var output = {"funnel_name": funnel.name, "step_counts": step_counts};
        emit(funnel.name, output);
        if("tests" in this.value){
            var tests = this.value.tests;
            for(id in tests){
                emit(funnel.name + ':' + id + ':' + tests[id], output);
            }
        }
    }, this);
""")

reduce3 = reduce_code("""
    var steps_dict = {};
    funnels.forEach(function(funnel){
        steps_dict[funnel.name] = funnel.steps;
    });

    var steps = steps_dict[values[0].funnel_name];

    var result = {};
    steps.forEach(function(step){
        result[step] = 0;
    });

    values.forEach(function(value) {
        steps.forEach(function(step){
            result[step] += value.step_counts[step];
        });
    });

    return {"funnel_name": values[0].funnel_name, "step_counts": result};
""")

if "events" not in db.collection_names():
    print "no data yet"
    exit()

db.events.map_reduce(map1, reduce1, "events_by_session")
db.sessions.map_reduce(map2, reduce2, {"reduce": "events_by_session"})
result = db.events_by_session.map_reduce(map3, reduce3, "funnel_data")
for doc in result.find():
    print doc
