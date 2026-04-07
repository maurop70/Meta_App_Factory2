import sys
sys.path.insert(0, '.')
from model_router import route as _model_route

def _call_agent(agent_name, topic):
    print(f'TEST calling {agent_name} direct via model_router...')
    try:
        result = _model_route('general', f'You are the {agent_name}. In 2 sentences: {topic}')
        print(f'{agent_name} responded: ' + (result[:100] if result else 'EMPTY'))
        return result
    except Exception as e:
        print(f'Error inside test: {e}')

if __name__ == "__main__":
    _call_agent('CMO', 'cross-chain liquidity aggregator')
