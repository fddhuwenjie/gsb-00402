
def main():
    # Exact match
    mbedtls_ssl_init()
    
    # Library prefix match (mbedtls_)
    mbedtls_mpi_init()
    
    # Prefix match
    mbedtls_ssl_conf_read_timeout()

if __name__ == "__main__":
    main()
