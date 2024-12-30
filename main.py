import os
from datetime import datetime, timezone, timedelta
import re
from typing import TypedDict, List
from github import Auth, Github


class PackageVersion(TypedDict):
    id: int
    created_at: str
    metadata: dict


class Package(TypedDict):
    id: int
    name: str
    version_count: int


TAMP_TAG = re.compile(r"^(temp|poc|feat|dev|debug)-.*$")


class GithubPackageCleaner:
    def __init__(self, token: str, org_name: str, container_prefix: str):
        """初始化 GitHub 包清理器

        Args:
            token: GitHub token
            org_name: 组织名称
            container_prefix: 容器名称前缀
        """
        self.github = Github(auth=Auth.Token(token))
        self.org_name = org_name
        self.container_prefix = container_prefix

    def get_packages(self) -> List[Package]:
        """获取所有匹配前缀的容器包"""
        headers, packages = self.github._Github__requester.requestJsonAndCheck(
            "GET", f"/orgs/{self.org_name}/packages", {"package_type": "container"}
        )

        return [
            pkg for pkg in packages if pkg["name"].startswith(self.container_prefix)
        ]

    def get_outdated_versions(self, pkg_name: str) -> List[PackageVersion]:
        """获取过期的包版本（超过30天且无标签）"""
        headers, versions = self.github._Github__requester.requestJsonAndCheck(
            "GET", f"/orgs/{self.org_name}/packages/container/{pkg_name}/versions"
        )

        one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)

        outdated = []
        for version in versions:
            created_at = datetime.strptime(
                version["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)

            tags = version["metadata"]["container"]["tags"]

            if created_at < one_month_ago and self.is_tags_safe_to_delete(tags):
                outdated.append(version)

        return outdated

    def is_tags_safe_to_delete(self, tags: list[str] | None) -> bool:
        if not tags:
            return True

        if len(tags) == 1:
            tag = tags[0]
            return TAMP_TAG.match(tag) is not None

        return False

    def delete_package_version(self, pkg_name: str, version_id: int) -> None:
        """删除指定的包版本"""
        print(f"正在删除 {pkg_name} 版本 {version_id}")

        self.github._Github__requester.requestJsonAndCheck(
            "DELETE",
            f"/orgs/{self.org_name}/packages/container/{pkg_name}/versions/{version_id}",
        )

    def clean_outdated_packages(self) -> None:
        """清理所有过期的包版本"""
        packages = self.get_packages()
        print(f"找到的包: {[p['name'] for p in packages]}")

        has_outdated = False

        for pkg in packages:
            outdated_versions = self.get_outdated_versions(pkg["name"])
            for version in outdated_versions:
                self.delete_package_version(pkg["name"], version["id"])
                has_outdated = True

        if has_outdated:
            print("清理完成")
        else:
            print("没有找到过期的包")


def main():
    # 从环境变量获取配置
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("需要设置 GITHUB_TOKEN 环境变量")

    org_name = os.getenv("GITHUB_ORG_NAME", "any-xi")
    container_prefix = os.getenv("CONTAINER_PREFIX", "writing-")

    # 创建清理器并执行清理
    cleaner = GithubPackageCleaner(token, org_name, container_prefix)
    cleaner.clean_outdated_packages()


if __name__ == "__main__":
    if os.getenv("DEBUG"):
        from dotenv import load_dotenv

        load_dotenv(".env.local")

    main()
