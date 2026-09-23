# IaaS, PaaS, and SaaS Responsibility Models

These small local labs compare **who manages what**. Docker Compose keeps the
examples reproducible, but it is not a cloud provider.

| Model | Student activity | Local analogy | Important limitation |
|---|---|---|---|
| IaaS | Administer an OS environment | Ubuntu container plus persistent disk | A container is not a VM and shares the host kernel |
| PaaS | Change application code | Platform-supplied Python runtime | Compose exposes more runtime detail than a real PaaS |
| SaaS | Use and configure a ready application | Adminer web application | The lab is self-hosted; a real provider operates SaaS for you |

Run one subfolder at a time because PaaS and SaaS both use port 8080.

Recommended order:

```text
iaas/  ->  paas/  ->  saas/
```

The amount of infrastructure visible to the student decreases at each step.
