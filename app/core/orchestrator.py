import os
import logging
from app.core.event_bus import EventBus
from app.core.failure_detector import FailureDetector
from app.agents.validator import run_validator, get_validator
from app.agents.ideation import run_ideation, set_tools
from app.agents.critic import run_critic
from app.agents.planner import run_planner
from app.memory.memory_service import MemoryService
from app.observability.langfuse_client import LangfuseClient
from app.tools.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class Orchestrator:

    def __init__(self, max_attempts=5):
        self.bus = EventBus()
        self.memory = MemoryService()
        self.failure_detector = FailureDetector(threshold=3)
        self.langfuse = LangfuseClient()
        self.max_attempts = max_attempts
        self._attempt_count = 0
        self._attempt_lock = threading.Lock()  # Thread safety для _attempt_count
        self.validator = get_validator()
        
        if not self.memory.db.check_connection():
            raise RuntimeError('Neo4j connection failed')
        
        self.tools = ToolRegistry(memory_service=self.memory, rag=self.memory.rag)
        set_tools(self.tools)

        self._register()

    def _register(self):
        self.bus.subscribe('START', self.ideation_node)
        self.bus.subscribe('IDEA_READY', self.critic_node)
        self.bus.subscribe('CRITIC_DONE', self.planner_node)

    def ideation_node(self, input_data):
        trace = self.langfuse.create_trace(name='orchestrator.ideation', input=input_data)

        try:
            idea = run_ideation(input_data, use_tools=True)
            
            if not idea or (isinstance(idea, dict) and 'error' in idea):
                raise ValueError(f"Invalid idea from LLM: {idea}")
            
            idea_id = self.memory.store_idea(idea, create_checkpoint=True)
            with self._attempt_lock:
                self._attempt_count += 1

            trace.update(output={'idea_id': idea_id}, metadata={'status': 'ok', 'attempt': self._attempt_count})

            return self.bus.emit('IDEA_READY', {'idea': idea, 'idea_id': idea_id, 'input': input_data})
        except Exception as e:
            logger.error(f'Ideation failed: {e}')
            trace.update(metadata={'status': 'error', 'error': str(e)})
            raise

    def critic_node(self, payload):
        with self._attempt_lock:
            attempt = self._attempt_count
        trace = self.langfuse.create_trace(
            name='orchestrator.critic',
            input=payload,
            metadata={'fail_count': self.failure_detector.get_fail_count(), 'attempt': attempt}
        )

        try:
            result = run_critic(payload['idea'])
            self.memory.store_evaluation(payload['idea_id'], result)

            score = result.get('final_score', 0)
            
            if score >= 5:
                self.failure_detector.reset()
                trace.update(metadata={'action': 'approved', 'score': score})

                return self.bus.emit('CRITIC_DONE', {
                    'idea': payload['idea'],
                    'idea_id': payload['idea_id'],
                    'critique': result
                })
            
            self.failure_detector.register_failure()
            
            with self._attempt_lock:
                current_attempt = self._attempt_count
            
            if current_attempt >= self.max_attempts:
                logger.warning(f"Max attempts ({self.max_attempts}) reached")
                trace.update(metadata={'action': 'max_attempts_reached', 'score': score})
                
                return self.bus.emit('CRITIC_DONE', {
                    'idea': payload['idea'],
                    'idea_id': payload['idea_id'],
                    'critique': result,
                    'warning': f'Max attempts reached ({self.max_attempts})'
                })
            
            logger.info(f"Idea score {score} < 5, generating new idea (attempt {current_attempt + 1})")
            trace.update(metadata={'action': 'regenerate', 'score': score})
            
            new_idea = run_ideation(payload['input'], use_tools=True)
            
            if not new_idea or (isinstance(new_idea, dict) and 'error' in new_idea):
                raise ValueError(f"Invalid regenerated idea: {new_idea}")
            
            new_id = self.memory.store_idea(new_idea, create_checkpoint=True)

            return self.bus.emit('IDEA_READY', {'idea': new_idea, 'idea_id': new_id, 'input': payload['input']})
            
        except Exception as e:
            logger.error(f'Critic failed: {e}')
            trace.update(metadata={'status': 'error', 'error': str(e)})
            raise

    def planner_node(self, payload):
        trace = self.langfuse.create_trace(name='orchestrator.planner', input=payload)

        try:
            plan = run_planner(payload['idea'])
            self.memory.store_plan(payload['idea_id'], plan)

            trace.update(output={'plan_length': len(str(plan))}, metadata={'status': 'ok'})

            return {
                'idea': payload['idea'],
                'critique': payload['critique'],
                'plan': plan
            }
        except Exception as e:
            logger.error(f'Planner failed: {e}')
            trace.update(metadata={'status': 'error', 'error': str(e)})
            raise

    def run(self, user_input):
        trace = self.langfuse.create_trace(name='orchestrator.run', input=user_input)
        with self._attempt_lock:
            self._attempt_count = 0

        try:
            # ВАЛИДАЦИЯ ЧЕРЕЗ ОТДЕЛЬНЫЙ АГЕНТ
            validation_result = run_validator(user_input)
            
            if not validation_result['is_valid']:
                logger.info(f"Request rejected by validator: {validation_result['reason']}")
                trace.update(metadata={
                    'status': 'rejected',
                    'reason': validation_result['reason'],
                    'category': validation_result['category']
                })
                return self.validator.get_stub_response()
            
            logger.info(f"Request accepted: {validation_result['reason']}")
            trace.update(metadata={'status': 'validated', 'category': 'STARTUP'})
            
            result = self.bus.emit('START', user_input)
            with self._attempt_lock:
                trace.update(output=result, metadata={'total_attempts': self._attempt_count})
            return result
        except Exception as e:
            logger.error(f'Orchestrator run failed: {e}')
            trace.update(metadata={'status': 'error', 'error': str(e)})
            # Сбрасываем счётчик попыток при ошибке
            with self._attempt_lock:
                self._attempt_count = 0
            raise
