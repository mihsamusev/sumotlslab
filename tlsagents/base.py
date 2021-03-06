import warnings
import copy
from typing import Callable
import traci
from feature_extraction import TLSDataPipeline


class TLSFactory:
	"""
	Factory class for creating TLS controllers
	"""
	registry = {}

	@classmethod
	def create_agent(cls, name: str, **kwargs) -> 'TLSAgent':
		"""
		Factory command to create a controller
		"""
		controller_class = cls.registry.get(name)
		controller = controller_class(**kwargs)
		return controller

	@classmethod
	def register_agent(cls, name: str) -> Callable:
		def inner_wrapper(wrapped_class: 'TLSAgent') -> Callable:
			if name in cls.registry:
				warnings.warn(f'TLS controller {name} already exists. Will replace it')
			cls.registry[name] = wrapped_class
			return wrapped_class
		return inner_wrapper


	@classmethod
	def get_registered_keys(cls):
		"""
		returns registered names
		"""
		return list(cls.registry.keys())

class TLSAgent:
	"""
	Abstract controller class
	"""
	def __init__(self, tls_id, constants=None, variables=None, data_query=None, optimizer=None):
		"""
		:tls_id - 
		:constants - dict
		:variables - dict
		:data_query: list
		:optimizer - object
		"""
		self.tls_id = tls_id
		self.tls_program = -1
		self.phase = 0
		self.phase_list = traci.trafficlight.getAllProgramLogics(
			self.tls_id)[self.tls_program].getPhases() # will break if pre-loaded tls
		self.n_phases = len(self.phase_list)
		self.elapsed = 0
		
		self.objectives = {}
		self.constants = constants
		self.variables = {}
		if variables:
			self.variables = copy.deepcopy(variables)

		self.data_pipeline = None
		if data_query and self.variables:
			self.data_pipeline =TLSDataPipeline(
				self.tls_id, self.tls_program, self.variables, data_query)
		
		self.optimizer = optimizer

	def next_phase_id(self):
		"""
		calculate id of next phase
		"""
		next_phase = (self.phase + 1) % self.n_phases
		if len(self.phase_list[self.phase].next) > 0:
			next_phase = self.phase_list[self.phase].next[0]
		return next_phase

	def calculate_next_phase(self):
		"""
		Here goes update logic using constants, 
		variables, data query and optimizer
		"""
		raise NotImplementedError

	def update_state(self):
		"""
		Given the updated logic the phases are continued and timed
		"""
		next_phase = self.calculate_next_phase()
		if self.phase == next_phase:
			self.elapsed += 1
		else:
			self.phase = next_phase
			self.elapsed = 0
			traci.trafficlight.setPhase(self.tls_id, self.phase)

	def decsribe_step(self):
		"""
		print all available tls data of the step
		"""
		return {
            "state": self.get_state(),
            "variables": self.get_variables(),
			"objectives": self.get_objectives(),
            }

	def get_objectives(self):
		return self.objectives

	def get_state(self):
		"""
		Return traffic signal state
		"""
		data = {
			"id": self.tls_id, 
			"phase": self.phase,
			"elapsed": self.elapsed
			}
		return data

	def get_variables(self):
		"""
		Returns variables
		"""
		return self.variables.copy()


@TLSFactory.register_agent('base_timed')
class TimedTLS(TLSAgent):
	"""
	Controller class model wrapping a standart
	SUMO pre-timed controller
	"""
	def __init__(self, tls_id, constants=None, variables=None, data_query=None, optimizer=None):
		super().__init__(tls_id, constants, variables, data_query, optimizer)

	def is_switch_time(self):
		dt = traci.trafficlight.getNextSwitch(self.tls_id) - traci.simulation.getTime()
		return int(dt) == 0

	def calculate_next_phase(self):
		next_phase = self.phase
		if self.is_switch_time():
			next_phase = self.next_phase_id()
		return next_phase


@TLSFactory.register_agent('base_recorded')
class RecordedTLS(TimedTLS):
	"""
	Controller class to replicated recorded sequence
	from a controller log
	"""
	def __init__(self, tls_id, constants=None, variables=None, data_query=None, optimizer=None):
		super().__init__(tls_id, constants, variables, data_query, optimizer)
		self.idx = 0

		self.phase_sequence = self.constants.get("sequence")
		assert self.phase_sequence is not None, \
			f"No key 'sequence' in constants for {self.tls_id}"
		self.phase = self.phase_sequence[self.idx]["phase"]
		self.recorded_length = len(self.phase_sequence)

	def calculate_next_phase(self):
		next_phase = self.phase
		if self.phase_sequence[self.idx]["duration"] == self.elapsed:
			self.idx += 1
			next_phase = self.phase_sequence[self.idx]["phase"]
		return next_phase


@TLSFactory.register_agent('base_crosswalk')
class CrosswalkTLS(TimedTLS):
	"""
	Controller class for a pedestrian responsive crosswalk controller
	"""
	def __init__(self, tls_id, constants=None, variables=None, data_query=None, optimizer=None):
		super().__init__(tls_id, constants, variables, data_query, optimizer)

		self.veh_phase_id = self.constants.get("veh_phase_id")
		if self.veh_phase_id is None:
			self.veh_phase_id = [
				i for i, p in enumerate(self.phase_list) if p.state.lower()[0]=='g'][0]

		self.min_green = self.constants.get("MIN_GREEN")
		if self.min_green is None:
			self.min_green = 15

		self.ped_key = list(self.variables)[0]

	def calculate_next_phase(self):
		next_phase = self.phase

		# read state
		self.variables = self.data_pipeline.extract()

		# check if request is sent during vehicle phase
		is_requested = False
		if self.phase == self.veh_phase_id:
			is_requested = self.variables[self.ped_key] > 0

			if self.elapsed > self.min_green and is_requested:
				next_phase = self.next_phase_id()
		else:
			next_phase = super().calculate_next_phase()
		return next_phase


