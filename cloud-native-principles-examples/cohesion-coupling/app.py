from high_cohesion import demo as high_cohesion
from low_cohesion import demo as low_cohesion
from loose_coupling import demo as loose_coupling
from tight_coupling import demo as tight_coupling

print("=== High Cohesion ===")
for line in high_cohesion():
    print(line)

print("\n=== Low Cohesion ===")
for line in low_cohesion():
    print(line)

print("\n=== Tight Coupling ===")
print(tight_coupling())

print("\n=== Loose Coupling ===")
for line in loose_coupling():
    print(line)
