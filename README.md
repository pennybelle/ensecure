Encrypted chat room!
![~ the void ~](/media/the_void.png?raw=true "ensecure client")

# Install
```sh
git clone https://github.com/pennybelle/ensecure.git
cd ensecure
```

# Build
First build the thing (only needs to be done on install and when updating)
#### Server
```sh
docker-compose build server
```
#### Client
```sh
docker-compose build client
```

# Use Server
Then use the thing (has to be done every time unfortunately)
### Start server
```sh
docker-compose up -d server
docker-compose attach server
```
- Press enter to init inputs
- Default ip is usually fine, same with port unless you are running multiple rooms/servers
- Set server password (only needs to be done on server init)
- When the console says "Waiting for connections..." you can detach from the container with CTRL+P then CTRL+Q
### Stop server
```sh
docker-compose down server
```
# Use Client
### Start client
```sh
docker-compose run --rm client
```
- Input IP of server you want to join (public IP if its over the internet!!)
- Then the port (press enter for default 27101 port)
- Enter a username for the room
- The client will generate 4096 RSA keys (only done once, reuses saved keys from then on)
- Then enter the password (only has to be done first time, saved to a .env)
- You will then be connected to the room!
### Stop client
- CTRL+C to leave the room (docker keeps it running so make sure to do this when you are done!)
- If container is left running (say if you crashed or detached), stop with
```sh
docker-compose down client
```