CC ?= cc
CFLAGS ?= -Os
BEARSSL_SRC_ROOT ?= ../../../../apps/bearssl-0.6/src
BEARSSL_INC_ROOT ?= ../../../../apps/bearssl-0.6/inc
CPPFLAGS += -DLOCAL_X86_BUILD -I. -I$(BEARSSL_SRC_ROOT) -I$(BEARSSL_INC_ROOT)
LDFLAGS ?=
LDLIBS ?=-lpthread

BUILD_DIR ?= build
HARNESS := harness
ATTACK_IMPL := attack.c

SOURCES=codec/ccopy.c int/i31_tmont.c int/i31_montmul.c int/i31_modpow.c int/i31_ninv31.c int/i31_muladd.c util/util.c int/i31_sub.c int/i31_add.c int/i32_div32.c
UUT_SOURCES := $(addprefix $(BEARSSL_SRC_ROOT)/,$(SOURCES))
LOCAL_SOURCES := context.c timing.c wrapper.c
HARNESS_SOURCES := harness.c $(LOCAL_SOURCES) $(ATTACK_IMPL) $(UUT_SOURCES)

HARNESS_OBJECTS := \
	$(addprefix $(BUILD_DIR)/,$(LOCAL_SOURCES:.c=.o)) \
	$(BUILD_DIR)/$(ATTACK_IMPL:.c=.o) \
	$(BUILD_DIR)/harness.o

.PHONY: all clean wrapper

all: $(HARNESS)

$(HARNESS): $(HARNESS_OBJECTS)
	$(CC) $(CFLAGS) $(CPPFLAGS) $(LDFLAGS) -o $@ $(HARNESS_OBJECTS) $(UUT_SOURCES) $(LDLIBS)

wrapper: $(BUILD_DIR)/wrapper.o

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/harness.o: harness.c context.h skeleton.h wrapper.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

$(BUILD_DIR)/wrapper.o: wrapper.c wrapper.h context.h timing.h $(UUT_SOURCES) | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

$(BUILD_DIR)/context.o: context.c context.h timing.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

$(BUILD_DIR)/timing.o: timing.c timing.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

$(BUILD_DIR)/attack.o: $(ATTACK_IMPL) skeleton.h context.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

$(ATTACK_IMPL):
	@printf '%s\n' "Missing $(ATTACK_IMPL). Generate or place the skeleton implementation in src/attack.c before building." >&2
	@false

clean:
	rm -rf $(BUILD_DIR) $(HARNESS)
