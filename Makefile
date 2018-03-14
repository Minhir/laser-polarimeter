all : proto

proto: Message.proto
	protoc --python_out=./ Message.proto
