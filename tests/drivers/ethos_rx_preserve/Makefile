# Draft regression app for RIOT #22606.
# Keep this native-first until the red test is proven.
BOARD ?= native64

include ../Makefile.drivers_common

USEMODULE += ethos
USEMODULE += test_utils_netdev_eth_minimal

INCLUDES += -I$(APPDIR)

include $(RIOTBASE)/Makefile.include
