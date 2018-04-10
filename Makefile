all : proto lib

proto: Message.proto
	protoc --python_out=./ Message.proto

lib:
	cd cpp && make


clean:
	cd cpp && make clean
