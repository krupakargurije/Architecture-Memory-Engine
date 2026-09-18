package com.example.ecommerce.repository;

import com.example.ecommerce.model.Order;
import org.springframework.stereotype.Repository;
import java.util.Optional;

@Repository
public interface OrderRepository {
    Order save(Order order);
    Optional<Order> findById(Long id);
    void deleteById(Long id);
}
