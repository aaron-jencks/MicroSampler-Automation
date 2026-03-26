ifneq ($(wildcard ../makefile),)
include ../makefile
endif

CC ?= cc
CFLAGS ?= -Os
BEARSSL_SRC_ROOT ?= ../../../../apps/bearssl-0.6/src
BEARSSL_INC_ROOT ?= ../../../../apps/bearssl-0.6/inc
CPPFLAGS += -I. -I$(BEARSSL_SRC_ROOT) -I$(BEARSSL_INC_ROOT)
LDFLAGS ?=
LDLIBS ?=

BUILD_DIR ?= build
HARNESS := harness
ATTACK_IMPL := attack.c

UUT_SOURCES := $(patsubst ../src/%,$(BEARSSL_SRC_ROOT)/%,$(SOURCES))
LOCAL_SOURCES := context.c timing.c wrapper.c
HARNESS_SOURCES := harness.c $(LOCAL_SOURCES) $(ATTACK_IMPL) $(UUT_SOURCES)
UUT_OBJECTS := $(addprefix $(BUILD_DIR)/,$(notdir $(UUT_SOURCES:.c=.o)))

HARNESS_OBJECTS := \
	$(addprefix $(BUILD_DIR)/,$(LOCAL_SOURCES:.c=.o)) \
	$(UUT_OBJECTS) \
	$(BUILD_DIR)/$(ATTACK_IMPL:.c=.o) \
	$(BUILD_DIR)/harness.o

.PHONY: all clean wrapper

all: $(HARNESS)

$(HARNESS): $(HARNESS_OBJECTS)
	$(CC) $(CFLAGS) $(CPPFLAGS) $(LDFLAGS) -o $@ $(HARNESS_OBJECTS) $(LDLIBS)

wrapper: $(BUILD_DIR)/wrapper.o $(UUT_OBJECTS)

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

$(BUILD_DIR)/%.o: $(BEARSSL_SRC_ROOT)/codec/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: $(BEARSSL_SRC_ROOT)/int/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: $(BEARSSL_SRC_ROOT)/util/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

$(ATTACK_IMPL):
	@printf '%s\n' "Missing $(ATTACK_IMPL). Generate or place the skeleton implementation in src/attack.c before building." >&2
	@false

clean:
	rm -rf $(BUILD_DIR) $(HARNESS)
