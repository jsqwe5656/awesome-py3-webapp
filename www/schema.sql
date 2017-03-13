-- schema.sql

-- 如果存在数据库则删除
drop database if exists awesome;
-- 重新创建数据库
create database awesome;
-- 使用数据库
use awesome;
-- 给数据库用户授权 如果没有该用户 mysql会自动创建一个
grant select,insert,update,delete on awesome.* to 'zbf'@'localhost' identified by '123456';

create table users(
    `id` varchar(50) not null,
    `email` varchar(50) not null,
    `passwd` varchar(50) not null,
    `admin` varchar(50) not null,
    `name` varchar(50) not null,
    `image` varchar(500) not null,
    `created_at` real not null,
    unique key `idx_email` (`email`),
    key `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table blogs(
    `id` varchar(50) not null,
    `user_id` varchar(50) not null,
    `user_name` varchar(50) not null,
    `user_image` varchar(500) not null,
    `name` varchar(50) not null,
    `sumary` varchar(50) not null,
    `content` varchar(50) not null,
    `created_at` real not null,
    key  `idx_created_at` (`created_at`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table comments(
    `id` varchar(50) not null,
    `blog_id` varchar(50) not null,
    `user_id` varchar(50) not null,
    `user_name` varchar(50) not null,
    `user_image` varchar(500) not null,
    `content` mediumtext not null,
    `created_at` real not null,
    key `idx_created_at` (`created_at`),
    primary key (`id`)
)engine=innodb default charset=utf8;



