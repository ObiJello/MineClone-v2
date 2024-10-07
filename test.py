# Open a file in write mode, or create it if it doesn't exist
with open("hello.txt", "w") as file:
    # Write "Hello" into the file
    file.write("Hello")

print("File 'hello.txt' has been created with the text 'Hello'.")
