import requests

def run_manual_chatbot_tests():
	# These are manual smoke tests that should only run when executed directly.
	response = requests.post('http://127.0.0.1:8000/api/chatbot/', json={'query': 'hello'})
	print('Status:', response.status_code)
	try:
		print('Response:', response.json())
	except Exception:
		print('Response body could not be parsed as JSON')

	# Test recommendation
	response2 = requests.post('http://127.0.0.1:8000/api/chatbot/', json={'query': 'recommend me a book'})
	print('Recommendation Status:', response2.status_code)
	try:
		print('Recommendation Response:', response2.json())
	except Exception:
		print('Recommendation response could not be parsed as JSON')


if __name__ == '__main__':
	run_manual_chatbot_tests()
