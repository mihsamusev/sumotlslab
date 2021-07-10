# sumotllab

Welcome to sumotllab - a SUMO based simulation environment to test and implement your traffic control algorithms.

[use this CircleCI example for documentation](https://circleci.com/docs/2.0/configuration-reference/)

## Table of Contents
1. [TLS Description](#paragraph1)

## Supported types of run

One network, one set of tls, N runs


## Demand generation

Demand is generated using `randomTrips.py`

For vehicles - binomial with `n = 5` and `p = peirod / 5 = 1/5`

```sh
python $SUMO_HOME/tools/randomTrips.py \
    -n data/block.net.xml \
    --weights-prefix data/edge_weights \
    -o data/vehicles.rou.xml \
    --seed 42 \
    --validate \
    -b 0 \
    -e 3000 \
    --binomial 5
```

For pedestrians - uniform every 5s
```sh
python $SUMO_HOME/tools/randomTrips.py \
    -n data/block.net.xml \
    -o data/pedestrians.rou.xml \
    --pedestrians \
    --max-distance 100 \
    --period 5 
```

## Separation of tasks 

Concrete TLSAgent implementation:
 - Sumbclass TLSAgent and implement `calclulate_next_phase()` method
 - Register the agent using `TLSFactory.register_agent(<agent_name>)`
 - 

Config manager ensures:
 - existence of compulsory configuration fields
 - valid formats, existsing file paths and executables are put in
 - recognition of your custom TLSAgent as a valid controller method


## TLS description <a name="paragraph1"></a>
```yml
id: # existence of ID not validated
controller: # validated
constants:
    - MIN_TIME: 15
variables: # data used for decision making that can update every step, store MPC 
extract:
    user_data:
        - user_data_extraction_query_1:
        ...
        - user_data_extraction_query_n:
    tls_data:
        - tls_data_extraction_query_1:
        ...
        - tls_data_extraction_query_m:
```

For example

```yml
id:
controller:
	class: CrosswalkTLS
	constants:
		MIN_TIME: 15
	variables:
		ped_count: 0
	extract:
        user_data:
		    - feature: count
		    user_type: pedestrian
			at: phase
			mapping:
				2: "ped_count" 
```

## Feature extraction queries

It is possible to extract both user_data as well as the traffic light data
```
```

### User data

```yml
user_data:
    - feature:    # can be [count, speed, eta, waiting_time]
	user_type:  # can be [pedestrian, cyclist, vehicle type]
  at:       # can be [lane, phase or detector]
  mapping:    # dict of mapping between "at" types to dict keys for output
    sumo_name_1: "variable_name_1"
    ...
    sumo_name_n: "variable_name_n"
```

for example, collect all pedestrians served during phases 0 and 1 of a tls

```yml
user_data:
    - feature: 'count'
	user_type: 'pedestrian'
	at: 'phase'
	mapping:
    0: 'p0'
    1: 'p1'
```

### tls_data
```yml
tls_data:
	- feature: elapsed_time # can be []
		to_var: x

```


### Using the feature extraction pipeline
If a query is provided to the TLS controller one can leverage
the `data_pipeline` class and the `extract()` method to 

```python
def calculate_next_phase()
	self.variables = self.data_pipeline.extract()

```

## Extend framework with your own agents
- New agent shall be saved in a `*.py` file under `tlsagents` directory
- New agent shall implement a custom `calculate_next_phase()` method
- New agent shall be registered using a decorator`TLSFactory.register_agent(<AGENTS_NAME>)`

Following example implements a controller that outputs a random phase each simulation step

```python
from tlsagents.base import TLSAgent, TLSFactory
import random

@TLSFactory.register_agent('my_new_ctrl')
class OneWeirdTLS(TLSAgent):
    def __init__(self, tls_id, constants=None, variables=None,
        data_query=None, optimizer=None):
        super().__init__(tls_id, constants, variables, data_query, optimizer)

    def calculate_next_phase(self):
        return random.randint(0, self.n_phases-1)
```

## Limitations / Details
- Single node intersections, no clusters
- No communications between TLS
- Will use last loaded traffic lights program, either initial or by `*.tll.xml`