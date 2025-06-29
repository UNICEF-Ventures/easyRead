from gradio_client import Client, handle_file

client = Client("https://scai.globalsymbols.com/")
result = client.predict(
		"Mulberry",
		"A red bus with a yellow stripe",
		None,
		"No",
		50,
		3,
		0.75,
		7.5,
		None, 
		api_name="/process_symbol_generation"
)
print(result)
