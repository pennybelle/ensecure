Encrypted chat room!
![~ the void ~](/media/the_void.png?raw=true "ensecure client")

# Prerequisites
You need Git to install and Docker (and docker-compose) to run this application.
## Linux
Download with your favorite package manager
#### Arch
```sh
pacman -S git docker docker-compose
```
#### Debian
```sh
dpkg -i git docker docker-compose
```
#### Alpine
```sh
apk add git docker docker-compose
```
#### Ubuntu and friends
```sh
apt install git docker docker-compose
```

Make sure to start the daemon before you try using the application!
```sh
sudo systemctl start docker
```

## Windows
#### GitHub Desktop
Just [download the GitHub Desktop app from their website](https://central.github.com/deployments/desktop/desktop/latest/win32).
Launch the app to install git on powershell. For the install process, use PowerShell to run the commands.
#### Docker Desktop
Just [download the Docker Desktop app from their website](https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe?utm_source=docker&utm_medium=webreferral&utm_campaign=dd-smartbutton&utm_location=module).
Launch the app to start the engine, wait for the app to report the engine has started, and then you're good!


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

# Use (Client)
Then use the thing (has to be done every time unfortunately)
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
# Use (Server)
If you want to run a room that people can connect to, use this! Make sure to port forward whatever port you use for your room if you want the room to be available over the web. Data transmission is encrypted with 4096 rsa encryption. If someone is connecting from outside your LAN, make sure they use [your public IPv4 address](https://whatismyipaddress.com/)!
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