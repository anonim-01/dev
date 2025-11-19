"""IP engelleme sistemi - BTK ve diğer kamu kurumları için"""
from __future__ import annotations

import ipaddress
from typing import List, Union

from flask import abort, request


class IPBlocker:
    """IP adresi engelleme sınıfı"""
    
    def __init__(self):
        # Engellenecek IP aralıkları (CIDR formatında)
        self.blocked_ranges: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = [
            # BTK (Bilgi Teknolojileri ve İletişim Kurumu)
            ipaddress.ip_network("185.67.32.0/22"),  # 185.67.32.0 - 185.67.35.255
            
            # Diğer BTK blokları (opsiyonel, gerekirse ekleyin)
            ipaddress.ip_network("185.67.35.0/24"),  # BTK BTD özel bloğu
            
            # Emniyet Genel Müdürlüğü (isteğe bağlı)
            # ipaddress.ip_network("195.174.134.0/24"),
            
            # Jandarma Genel Komutanlığı (isteğe bağlı)
            # ipaddress.ip_network("212.156.70.0/24"),
        ]
        
        # Engellenecek tekil IP'ler
        self.blocked_ips: List[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]] = []
    
    def is_blocked(self, ip_str: str) -> bool:
        """
        Verilen IP adresinin engellenip engellenmediğini kontrol eder
        
        Args:
            ip_str: Kontrol edilecek IP adresi (string formatında)
            
        Returns:
            bool: IP engellenmiş ise True, değilse False
        """
        try:
            ip = ipaddress.ip_address(ip_str)
            
            # Tekil IP kontrolü
            if ip in self.blocked_ips:
                return True
            
            # IP aralığı kontrolü
            for network in self.blocked_ranges:
                if ip in network:
                    return True
            
            return False
        except ValueError:
            # Geçersiz IP formatı
            return False
    
    def add_ip(self, ip_str: str) -> None:
        """Tekil IP ekle"""
        try:
            ip = ipaddress.ip_address(ip_str)
            if ip not in self.blocked_ips:
                self.blocked_ips.append(ip)
        except ValueError:
            pass
    
    def add_range(self, cidr: str) -> None:
        """IP aralığı ekle (CIDR formatında, örn: 192.168.1.0/24)"""
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            if network not in self.blocked_ranges:
                self.blocked_ranges.append(network)
        except ValueError:
            pass
    
    def remove_ip(self, ip_str: str) -> None:
        """Tekil IP çıkar"""
        try:
            ip = ipaddress.ip_address(ip_str)
            if ip in self.blocked_ips:
                self.blocked_ips.remove(ip)
        except ValueError:
            pass


# Global IP blocker instance
ip_blocker = IPBlocker()


def get_client_ip() -> str:
    """
    İstemcinin gerçek IP adresini alır (proxy/load balancer arkasında bile)
    """
    # Cloudflare kullanıyorsanız
    if "CF-Connecting-IP" in request.headers:
        return request.headers["CF-Connecting-IP"]
    
    # Diğer reverse proxy'ler
    if "X-Forwarded-For" in request.headers:
        # İlk IP gerçek client IP'sidir
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    
    if "X-Real-IP" in request.headers:
        return request.headers["X-Real-IP"]
    
    # Doğrudan bağlantı
    return request.remote_addr or "0.0.0.0"


def check_ip_blocked():
    """
    Mevcut isteğin IP'sini kontrol eder ve engellenmiş ise erişimi reddeder.
    Flask before_request hook olarak kullanılır.
    """
    client_ip = get_client_ip()
    
    if ip_blocker.is_blocked(client_ip):
        # 403 Forbidden döndür
        abort(403)


__all__ = ["IPBlocker", "ip_blocker", "get_client_ip", "check_ip_blocked"]
