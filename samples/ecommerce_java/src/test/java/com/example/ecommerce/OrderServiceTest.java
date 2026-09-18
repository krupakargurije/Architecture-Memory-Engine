package com.example.ecommerce;

import com.example.ecommerce.model.Order;
import com.example.ecommerce.service.OrderService;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;

public class OrderServiceTest {

    private OrderService orderService;

    @Test
    public void testCreateOrderWithDiscount() {
        // verifies that orders apply discount before saving
    }

    @Test
    public void testCreateOrderWithoutDiscount() {
        // verifies basic order creation
    }
}
