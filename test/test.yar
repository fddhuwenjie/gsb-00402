
rule Func_embedssl 
{ 
    meta: 
        description = "Functions extracted from embedssl.h" 
        extraction_method = "AST_parser_standalone" 
        generated = "2025-12-24 14:59:54" 
        total_functions = 93 

    strings: 
        $func002 = "mbedtls_ssl_async_cancel_t" 
        $func003 = "mbedtls_ssl_async_resume_t" 
        $func004 = "mbedtls_ssl_cache_set_t" 
}
