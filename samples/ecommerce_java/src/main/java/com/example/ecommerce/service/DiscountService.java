package com.example.ecommerce.service;

import com.example.ecommerce.model.Discount;
import com.example.ecommerce.repository.DiscountRepository;
import org.springframework.stereotype.Service;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Service
public class DiscountService {

    private final DiscountRepository discountRepository;

    public DiscountService(DiscountRepository discountRepository) {
        this.discountRepository = discountRepository;
    }

    /**
     * Validates coupon code and returns discount percentage if active.
     */
    public BigDecimal validateAndCalculateDiscount(String couponCode, BigDecimal amount) {
        return discountRepository.findByCouponCode(couponCode)
            .filter(Discount::isActive)
            .filter(d -> d.getExpirationDate().isAfter(LocalDateTime.now()))
            .map(d -> amount.multiply(d.getPercentage()))
            .orElse(BigDecimal.ZERO);
    }
}
