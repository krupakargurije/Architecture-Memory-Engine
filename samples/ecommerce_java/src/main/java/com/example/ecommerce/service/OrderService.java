package com.example.ecommerce.service;

import com.example.ecommerce.model.Order;
import com.example.ecommerce.repository.OrderRepository;
import org.springframework.stereotype.Service;
import java.math.BigDecimal;

@Service
public class OrderService {

    private final OrderRepository orderRepository;
    private final DiscountService discountService;

    public OrderService(OrderRepository orderRepository, DiscountService discountService) {
        this.orderRepository = orderRepository;
        this.discountService = discountService;
    }

    /**
     * Creates a new customer order after applying discounts.
     */
    public Order createOrder(String customerId, BigDecimal baseTotal, String couponCode) {
        BigDecimal discount = BigDecimal.ZERO;
        if (couponCode != null && !couponCode.isBlank()) {
            discount = discountService.validateAndCalculateDiscount(couponCode, baseTotal);
        }

        Order order = new Order();
        order.setCustomerId(customerId);
        order.setTotalAmount(baseTotal.subtract(discount));
        order.setStatus("CREATED");

        return orderRepository.save(order);
    }
}
