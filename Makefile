ifeq ($(strip $(DEVKITPPC)),)
$(error "Please set DEVKITPPC in your environment. export DEVKITPPC=<path to>devkitPPC)
endif

.SUFFIXES:

include $(DEVKITPPC)/wii_rules

TARGET	= ftpii
SOURCES	= source
DATA	= data
BUILD	= build

# Old code base: keep pointer/int mismatches in the 2010 devoptab drivers as warnings,
# use common symbols as GCC < 10 did, and the C dialect the code was written for.
CFLAGS				= -g -O2 -Wall -std=gnu17 -fcommon -Wno-error=incompatible-pointer-types -Wno-error=int-conversion $(MACHDEP) $(INCLUDE)
LDFLAGS				= -L$(LIBOGC_LIB) -lwiiuse -lbte -lfat -logc -lm -g $(MACHDEP) -Wl,-Map,$(notdir $@).map,--section-start,.init=0x80a00000
PRELOADER_LDFLAGS	= -L$(LIBOGC_LIB) -logc -g $(MACHDEP) -Wl,-Map,$(notdir $@).map

ifneq ($(BUILD),$(notdir $(CURDIR)))

export OUTPUT	:= $(CURDIR)/$(TARGET)
export VPATH	:= $(foreach dir,$(SOURCES) $(DATA),$(CURDIR)/$(dir))
export DEPSDIR	:= $(CURDIR)/$(BUILD)
export LD		:= $(CC)

export OFILES			:= certs.bin.o su_tik.bin.o su_tmd.bin.o compat.o ui.o reset.o pad.o net.o \
						   iospatch.o isfs.o otp.o mini_seeprom.o seeprom.o fs.o ftp.o loader.o vrt.o dol.o ftpii.o
export PRELOADER_OFILES	:= _$(TARGET).dol.o dol.o preloader.o
export INCLUDE			:= -I$(CURDIR)/$(BUILD) -I$(LIBOGC_INC)

.PHONY: $(BUILD) clean run

$(BUILD):
	@[ -d $@ ] || mkdir -p $@
	@$(MAKE) --no-print-directory -C $(BUILD) -f $(CURDIR)/Makefile

clean:
	@rm -rf $(BUILD) $(TARGET).dol $(TARGET).elf

run:
	@wiiload $(TARGET).dol

else

$(OUTPUT).dol: $(OUTPUT).elf

$(OUTPUT).elf: $(PRELOADER_OFILES)
	@echo linking ... $(notdir $@)
	@$(LD) $^ $(PRELOADER_LDFLAGS) -o $@

%.dol.o: %.dol
	@$(bin2o)

%.bin.o: %.bin
	@echo $(notdir $<)
	@$(bin2o)

isfs.o: certs.bin.o su_tik.bin.o su_tmd.bin.o

_$(TARGET).elf: $(OFILES)

DEPENDS = $(OFILES:.o=.d) $(PRELOADER_OFILES:.o=.d)
-include $(DEPENDS)

endif
