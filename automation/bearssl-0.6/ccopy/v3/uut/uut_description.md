The algorithm under test is a simple constant-time copy method displayed below:

```c
/**
static inline uint32_t
MUX(uint32_t ctl, uint32_t x, uint32_t y)
{
	return y ^ (-ctl & (x ^ y));
}
*/
void
br_ccopy(uint32_t ctl, void *dst, const void *src, size_t len)
{
	unsigned char *d;
    	const unsigned char *s;
	d = dst;
	s = src;
	while (len -- > 0) {
		uint32_t x, y;

		x = *s ++;
		y = *d;
		*d = MUX(ctl, x, y);
		d ++;
	}
}
```

You should use this to guide your ideas and implementation.