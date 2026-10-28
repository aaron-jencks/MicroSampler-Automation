#include <gmp.h>
#include <mpfr.h>
#include <mpc.h>
#include <zlib.h>
int main(){mpz_t z;mpz_init(z);mpz_clear(z);mpfr_t f;mpfr_init2(f,53);mpfr_clear(f);mpc_t c;mpc_init2(c,53);mpc_clear(c);return zlibVersion()?0:1;}
