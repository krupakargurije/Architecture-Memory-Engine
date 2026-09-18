package com.example.ecommerce.service;

import com.example.ecommerce.model.Product;
import com.example.ecommerce.repository.PricingRepository;
import org.springframework.stereotype.Service;
import java.math.BigDecimal;

@Service
public class PricingService {

    private final PricingRepository pricingRepository;

    public PricingService(PricingRepository pricingRepository) {
        this.pricingRepository = pricingRepository;
    }

    /**
     * Retrieves product price quote.
     */
    public BigDecimal calculateQuote(String sku, int quantity) {
        Product product = pricingRepository.findBySku(sku)
            .orElseThrow(() -> new IllegalArgumentException("Product not found: " + sku));
        return product.getBasePrice().multiply(BigDecimal.valueOf(quantity));
    }
}
