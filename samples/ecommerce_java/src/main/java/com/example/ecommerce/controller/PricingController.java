package com.example.ecommerce.controller;

import com.example.ecommerce.service.PricingService;
import org.springframework.web.bind.annotation.*;
import java.math.BigDecimal;

@RestController
@RequestMapping("/api/pricing")
public class PricingController {

    private final PricingService pricingService;

    public PricingController(PricingService pricingService) {
        this.pricingService = pricingService;
    }

    @GetMapping("/quote")
    public BigDecimal getQuote(@RequestParam String sku, @RequestParam(defaultValue = "1") int quantity) {
        return pricingService.calculateQuote(sku, quantity);
    }
}
