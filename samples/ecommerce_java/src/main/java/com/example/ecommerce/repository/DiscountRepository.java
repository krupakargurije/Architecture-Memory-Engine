package com.example.ecommerce.repository;

import com.example.ecommerce.model.Discount;
import org.springframework.stereotype.Repository;
import java.util.Optional;

@Repository
public interface DiscountRepository {
    Optional<Discount> findByCouponCode(String couponCode);
    Discount save(Discount discount);
}
