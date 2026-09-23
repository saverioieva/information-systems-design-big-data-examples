# IaaS Responsibility Analogy

You receive an operating-system environment and administer it yourself. The
named volume represents persistent block storage supplied by the provider.

> This is a local analogy. The Ubuntu container is not a virtual machine and
> still shares the Docker host kernel.

## Start the environment

```bash
cd service-models/iaas
docker compose up -d
docker compose exec vm bash
```

Inside the environment, inspect and modify the OS:

```bash
cat /etc/os-release
apt-get update
apt-get install -y curl
echo "persistent IaaS data" > /srv/data/example.txt
cat /srv/data/example.txt
exit
```

You chose and installed the software. This represents the control and
operational responsibility associated with IaaS.

## Replace the compute instance

```bash
docker compose rm -sf vm
docker compose up -d
docker compose exec vm cat /srv/data/example.txt
```

The installed package disappears with the old container, while the file remains
on the named volume.

## Clean up

```bash
docker compose down -v
```
