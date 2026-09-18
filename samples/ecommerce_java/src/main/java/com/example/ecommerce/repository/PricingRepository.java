package com.example.ecommerce.repository;

import com.example.ecommerce.model.Product;
import org.springframework.stereotype.Repository;
import java.util.Optional;

@Repository
public interface PricingRepository {
    Optional<Product> findBySku(String sku);
    Product save(Product product);
}
